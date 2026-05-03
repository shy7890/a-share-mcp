# a-share-mcp

A 股行情远程 MCP 服务（FastMCP + akshare，SSE transport）。

## Tools
- `get_stock_price(symbol, days=30)` — 日线行情；`days` 默认 30，最大 1000；> 90 天自动走腾讯源
- `get_stock_financial(symbol)` — 财务摘要
- `get_stock_realtime(symbol)` — 实时行情快照（雪球单股接口）

所有工具带 TTL 内存缓存：日线 5 分钟、财务 1 小时、实时 20 秒。
失败自动重试 3 次（间隔 2s）。

## Run
```bash
pip install -r requirements.txt
python server.py
```

默认监听 `0.0.0.0:8000`，SSE endpoint: `/sse`。

## Deploy
Procfile 已配置，可直接部署到 Railway / Heroku 等平台。
