import os
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps

import akshare as ak
import pandas as pd
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("a-share-mcp")

mcp = FastMCP("a-share-mcp")

MAX_RETRIES = 3
RETRY_DELAY = 2.0


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


def _sina_symbol(symbol: str) -> str:
    s = symbol.strip().lower()
    if s.startswith(("sh", "sz", "bj")):
        return s
    if s.startswith("6"):
        return "sh" + s
    if s.startswith(("0", "3")):
        return "sz" + s
    if s.startswith(("4", "8")):
        return "bj" + s
    return s


@mcp.tool
@with_retry
def get_stock_price(symbol: str) -> dict:
    """查询A股近30个交易日日线行情。symbol 形如 600096。"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start,
        end_date=end,
        adjust="",
    )
    return {
        "ok": True,
        "symbol": symbol,
        "count": min(len(df), 30),
        "data": _df_records(df.tail(30)),
    }


@mcp.tool
@with_retry
def get_stock_financial(symbol: str) -> dict:
    """查询A股财务摘要。symbol 形如 600096。"""
    df = ak.stock_financial_abstract(symbol=symbol)
    return {"ok": True, "symbol": symbol, "data": _df_records(df)}


@mcp.tool
@with_retry
def get_stock_realtime(symbol: str) -> dict:
    """查询A股实时行情快照（新浪数据源）。symbol 形如 600096。"""
    df = ak.stock_zh_a_spot()
    sina = _sina_symbol(symbol)
    row = df[df["代码"] == sina]
    if row.empty:
        row = df[df["代码"].str.endswith(symbol)]
    if row.empty:
        return {"ok": False, "symbol": symbol, "error": "symbol not found"}
    return {"ok": True, "symbol": symbol, "data": _df_records(row)[0]}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
