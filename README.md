# a-share-mcp

远程 MCP 服务（FastMCP + akshare，SSE transport）。覆盖 A 股行情 + GitHub Trending。

## A 股工具
- `get_stock_price(symbol, days=30)` — 日线行情；`days` 默认 30，最大 1000；> 90 天自动走腾讯源
- `get_stock_financial(symbol)` — 财务摘要
- `get_stock_realtime(symbol)` — 实时行情快照（雪球单股接口）

## GitHub 工具
- `get_github_trending(language="", period="daily", limit=25)` — Trending 榜单；period 支持 daily / weekly / monthly
- `get_github_repo(repo)` — 仓库元信息（star、fork、license、最近活动等）；repo 形如 `owner/name`

## 行为细节
- 所有工具带 TTL 内存缓存：A 股日线 5 分钟 / 财务 1 小时 / 实时 20 秒；GitHub trending 30 分钟 / repo 详情 10 分钟
- 失败自动重试 3 次（间隔 2s）
- 设置环境变量 `GITHUB_TOKEN` 可提高 GitHub API 速率上限

## Run
```bash
pip install -r requirements.txt
python server.py
```

默认监听 `0.0.0.0:8000`，SSE endpoint: `/sse`。

## Deploy
Procfile 已配置，可直接部署到 Railway / Heroku 等平台。
