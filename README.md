# a-share-mcp

远程 MCP 服务（FastMCP + akshare，SSE transport）。覆盖 A 股行情 + GitHub Trending。

## A 股 — 行情类
- `get_stock_price(symbol, days=30)` — 日线行情；`days` 默认 30，最大 1000；> 90 天自动走腾讯源
- `get_stock_realtime(symbol)` — 实时行情快照（雪球单股接口）
- `get_stock_info(symbol)` — 个股基本信息（市值、流通股、行业、上市日期等）

## A 股 — 资金/筹码
- `get_stock_fund_flow(symbol, days=10)` — 个股资金流向（主力净流入、超大单等）
- `get_north_fund_flow(days=30)` — 北向资金历史净流入
- `get_lhb_detail(date)` — 龙虎榜详情（指定日期）

## A 股 — 信息/研报
- `get_stock_news(symbol, limit=20)` — 个股相关新闻（东方财富）
- `get_stock_notice(symbol, date)` — 股票公告
- `get_research_reports(symbol, limit=20)` — 个股研究报告
- `get_stock_financial(symbol)` — 财务摘要

## A 股 — 市场全局
- `get_index_realtime(category)` — 主要指数实时（上证/深证/中证）
- `get_sector_ranking(category)` — 板块涨跌排行（industry / concept）
- `get_hot_stocks(limit=30)` — 全市场热度榜

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
