# a-share-mcp

A 股行情远程 MCP 服务（FastMCP + akshare，SSE transport）。

## Tools
- `get_stock_price(symbol)` — 近 30 日日线行情
- `get_stock_financial(symbol)` — 财务摘要
- `get_stock_realtime(symbol)` — 实时行情快照

## Run
```bash
pip install -r requirements.txt
python server.py
```

默认监听 `0.0.0.0:8000`，SSE endpoint: `/sse`。

## Deploy
Procfile 已配置，可直接部署到 Railway / Heroku 等平台。
