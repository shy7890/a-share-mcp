import os
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("a-share-mcp")

mcp = FastMCP("a-share-mcp")

MAX_RETRIES = 3
RETRY_DELAY = 2.0
DEFAULT_DAYS = 30
MAX_DAYS = 1000

CACHE_TTL_PRICE = 300
CACHE_TTL_FINANCIAL = 3600
CACHE_TTL_REALTIME = 20
CACHE_TTL_TRENDING = 1800
CACHE_TTL_REPO = 600

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TRENDING_PERIODS = {"daily", "weekly", "monthly"}


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d")
    return json.loads(safe.to_json(orient="records", force_ascii=False, date_format="iso"))


def with_retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_err = e
                log.warning("%s attempt %d/%d failed: %s", func.__name__, attempt, MAX_RETRIES, e)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
        return {
            "ok": False,
            "error": type(last_err).__name__,
            "message": str(last_err),
            "attempts": MAX_RETRIES,
        }

    return wrapper


def ttl_cache(ttl_seconds: int):
    def decorator(func):
        store: dict = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            hit = store.get(key)
            if hit and (now - hit[0]) < ttl_seconds:
                return hit[1]
            val = func(*args, **kwargs)
            if isinstance(val, dict) and val.get("ok"):
                store[key] = (now, val)
            return val

        return wrapper

    return decorator


def _xq_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.startswith(("SH", "SZ", "BJ")):
        return s
    if s.startswith("6"):
        return "SH" + s
    if s.startswith(("0", "3")):
        return "SZ" + s
    if s.startswith(("4", "8")):
        return "BJ" + s
    return s


def _bare_symbol(symbol: str) -> str:
    s = symbol.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


@mcp.tool
@ttl_cache(CACHE_TTL_PRICE)
@with_retry
def get_stock_price(symbol: str, days: int = DEFAULT_DAYS) -> dict:
    """查询A股日线行情。

    symbol 形如 600519 或 sh600519 / sz000001。
    days 取最近 N 个交易日，默认 30，最大 1000。
    数据源：东方财富（默认）；days > 90 时自动切到腾讯，覆盖更长历史。
    """
    days = max(1, min(int(days), MAX_DAYS))
    bare = _bare_symbol(symbol)

    if days <= 90:
        source = "eastmoney"
        end = datetime.now().strftime("%Y%m%d")
        lookback = int(days * 1.6) + 30
        start = (datetime.now() - timedelta(days=lookback)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=bare,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="",
        )
    else:
        source = "tencent"
        df = ak.stock_zh_a_hist_tx(
            symbol=_xq_symbol(symbol).lower(),
            adjust="",
        )

    if df is None or df.empty:
        return {"ok": False, "symbol": symbol, "error": "no data returned"}

    tail = df.tail(days)
    return {
        "ok": True,
        "symbol": symbol,
        "source": source,
        "days_requested": days,
        "count": len(tail),
        "data": _df_records(tail),
    }


@mcp.tool
@ttl_cache(CACHE_TTL_FINANCIAL)
@with_retry
def get_stock_financial(symbol: str) -> dict:
    """查询A股财务摘要。symbol 形如 600519。"""
    bare = _bare_symbol(symbol)
    df = ak.stock_financial_abstract(symbol=bare)
    return {"ok": True, "symbol": symbol, "data": _df_records(df)}


@mcp.tool
@ttl_cache(CACHE_TTL_REALTIME)
@with_retry
def get_stock_realtime(symbol: str) -> dict:
    """查询A股实时行情快照（雪球单股接口，秒级返回）。symbol 形如 600519。"""
    xq = _xq_symbol(symbol)
    df = ak.stock_individual_spot_xq(symbol=xq)
    if df is None or df.empty:
        return {"ok": False, "symbol": symbol, "error": "symbol not found"}
    records = _df_records(df)
    if not records:
        return {"ok": False, "symbol": symbol, "error": "empty response"}
    return {"ok": True, "symbol": symbol, "source": "xueqiu", "data": records[0]}


@mcp.tool
@ttl_cache(CACHE_TTL_TRENDING)
@with_retry
def get_github_trending(language: str = "", period: str = "daily", limit: int = 25) -> dict:
    """获取 GitHub Trending 榜单。

    language: 语言筛选，留空表示全部；常见值：python / javascript / typescript / rust / go / cpp / java
    period: daily / weekly / monthly，默认 daily
    limit: 返回前 N 个仓库，默认 25，最大 25
    """
    period = period.lower()
    if period not in TRENDING_PERIODS:
        return {"ok": False, "error": f"period must be one of {sorted(TRENDING_PERIODS)}"}
    limit = max(1, min(int(limit), 25))
    lang = language.strip().lower()
    url = f"https://github.com/trending/{lang}" if lang else "https://github.com/trending"

    r = requests.get(url, params={"since": period}, headers={"User-Agent": UA}, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    repos = []
    for art in soup.select("article.Box-row")[:limit]:
        h2_a = art.select_one("h2 a")
        if not h2_a:
            continue
        full_name = " ".join(h2_a.get_text().split()).replace(" / ", "/")
        desc_el = art.select_one("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        lang_el = art.select_one("span[itemprop='programmingLanguage']")
        repo_lang = lang_el.get_text(strip=True) if lang_el else ""
        link_muteds = art.select("a.Link--muted")
        stars = link_muteds[0].get_text(strip=True).replace(",", "") if link_muteds else ""
        forks = link_muteds[1].get_text(strip=True).replace(",", "") if len(link_muteds) > 1 else ""
        added_el = art.select_one("span.d-inline-block.float-sm-right")
        stars_added = " ".join(added_el.get_text().split()) if added_el else ""
        repos.append({
            "name": full_name,
            "url": "https://github.com/" + full_name,
            "description": desc,
            "language": repo_lang,
            "stars": stars,
            "forks": forks,
            "stars_added": stars_added,
        })

    return {
        "ok": True,
        "language": lang or "all",
        "period": period,
        "count": len(repos),
        "data": repos,
    }


@mcp.tool
@ttl_cache(CACHE_TTL_REPO)
@with_retry
def get_github_repo(repo: str) -> dict:
    """查询 GitHub 仓库详情。repo 形如 owner/name，例如 anthropics/claude-code。"""
    repo = repo.strip().strip("/")
    if "/" not in repo:
        return {"ok": False, "error": "repo must be in 'owner/name' format"}

    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=10)
    if r.status_code == 404:
        return {"ok": False, "error": "repo not found"}
    r.raise_for_status()
    d = r.json()
    return {
        "ok": True,
        "data": {
            "name": d.get("full_name"),
            "description": d.get("description"),
            "language": d.get("language"),
            "stars": d.get("stargazers_count"),
            "forks": d.get("forks_count"),
            "watchers": d.get("subscribers_count"),
            "open_issues": d.get("open_issues_count"),
            "topics": d.get("topics", []),
            "homepage": d.get("homepage"),
            "url": d.get("html_url"),
            "created": d.get("created_at"),
            "updated": d.get("updated_at"),
            "pushed": d.get("pushed_at"),
            "license": (d.get("license") or {}).get("spdx_id"),
            "default_branch": d.get("default_branch"),
        },
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
