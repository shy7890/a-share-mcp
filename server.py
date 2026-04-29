import os
import json
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
from fastmcp import FastMCP

mcp = FastMCP("a-share-mcp")


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d")
    return json.loads(safe.to_json(orient="records", force_ascii=False, date_format="iso"))


@mcp.tool
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
    return {"symbol": symbol, "count": min(len(df), 30), "data": _df_records(df.tail(30))}


@mcp.tool
def get_stock_financial(symbol: str) -> dict:
    """查询A股财务摘要。symbol 形如 600096。"""
    df = ak.stock_financial_abstract(symbol=symbol)
    return {"symbol": symbol, "data": _df_records(df)}


@mcp.tool
def get_stock_realtime(symbol: str) -> dict:
    """查询A股实时行情快照。symbol 形如 600096。"""
    df = ak.stock_zh_a_spot_em()
    row = df[df["代码"] == symbol]
    if row.empty:
        return {"symbol": symbol, "error": "symbol not found"}
    return {"symbol": symbol, "data": _df_records(row)[0]}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
