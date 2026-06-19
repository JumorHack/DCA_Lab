# DCA Lab · 定投收益回测

面向 **A股 / 港股 / 美股 / 场内 ETF** 的「按月定投」收益回测网页。输入标的、起止月份与定投策略，
即可计算 **原始本金、当前价值、分红金额、平均年化(XIRR)**，支持「分红再投入 / 不复投」两种模式，
并以数字滚动卡片 + ECharts 动画曲线展示，所有行情/分红数据本地 SQLite 缓存，二次查询毫秒级返回。

## 功能特性

- 多市场：A股、港股、美股、场内 ETF；名称或代码模糊搜索。
- 两种定投策略：
  - 按固定金额：每月按「每手股数」买入最大整数手，**不足金额自动滚存至下月**。
  - 按固定股数：每月买入固定股数。
- 两种分红模式：分红再投入（复投）/ 不复投（现金累计）。
- 输出：原始本金、当前价值、分红金额、平均年化收益（XIRR，资金加权）、总收益率、逐期明细。
- 动画：结果卡片数字滚动、增长曲线入场动画、「按月播放」渐进展示积累过程、模式切换平滑过渡。
- 本地缓存：行情/分红/标的清单写入本地 SQLite，增量补抓，避免重复请求数据源。

## 技术栈

- 后端：FastAPI + akshare + pandas + SQLAlchemy(SQLite)
- 前端：React + TypeScript + Vite + Tailwind CSS + ECharts + framer-motion

## 目录结构

```
DCA_Agent/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口 + CORS
│   │   ├── markets.py         # 市场配置(手数/币种)
│   │   ├── db.py              # SQLite 持久缓存层
│   │   ├── models.py          # pydantic 模型
│   │   ├── services/
│   │   │   ├── data.py        # akshare 封装 + DB 优先缓存
│   │   │   ├── engine.py      # 定投模拟引擎
│   │   │   └── xirr.py        # 年化(XIRR)
│   │   └── api/
│   │       ├── search.py      # /api/search, /api/markets
│   │       └── backtest.py    # /api/backtest
│   ├── data/dca_cache.sqlite  # 本地缓存(自动生成)
│   └── requirements.txt
└── frontend/                  # Vite + React 前端
```

## 环境要求

- Python ≥ 3.9（已在 3.13 验证）
- Node.js ≥ 18
- 可访问外网（akshare 行情来源为东方财富/新浪）

## 快速开始

### 一键启动（推荐）

在项目根目录执行，脚本会自动创建/激活 Python 虚拟环境、安装前后端依赖并同时启动：

```bash
./start.sh
```

启动后打开 http://localhost:5173 即可；按 `Ctrl+C` 会同时关闭前后端。

可选环境变量：

```bash
BACKEND_PORT=8020 FRONTEND_PORT=5180 ./start.sh   # 自定义端口
REINSTALL=1 ./start.sh                             # 强制重装依赖
```

> 首次运行会安装依赖、且后端加载 akshare 约需 20-30s，请耐心等待。
> 如提示端口被占用，用 `BACKEND_PORT=<其他端口> ./start.sh` 重试。

---

### 手动启动

#### 1) 后端（端口 8010）

```bash
cd backend

# 方式 A：uv（更快）
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 方式 B：标准 pip
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

> 说明：默认使用 8010 端口（8000 常被其他服务占用）。如需更换端口，记得同步修改
> `frontend/vite.config.ts` 中的代理 `target`。

#### 2) 前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可使用。Vite 已将 `/api` 代理到后端 `http://localhost:8010`。

## 使用说明

1. 选择市场（A股/港股/美股/ETF）。
2. 搜索并选择股票或 ETF（也可直接输入代码；美股可输入 `AAPL` 或 `105.AAPL`）。
3. 设置开始/结束月份、定投策略与每月金额（或股数）。
4. 选择分红处理方式（再投入 / 不复投），点击「开始回测」。
5. 查看四项核心指标、增长曲线（可「按月播放」）与定投明细。切换复投模式会自动重算。

## 计算口径

- **当前价值**：结束月最后交易日的持仓市值（+ 不复投现金 + 未投入滚存现金）。
- **平均年化**：XIRR（资金加权内部收益率），更适合不定期定投；同时展示总收益率。
- **复投价值**：采用后复权(hfq)闭式 `Σ 投入ᵢ × P_hfq(end)/P_hfq(tᵢ)`，自动包含拆送与分红再投，跨市场稳健。
- **币种**：按各市场原币种（CNY/HKD/USD），不做汇率换算。
- 忽略交易佣金、印花税与红利税（分红为税前金额）。

## 数据可靠性说明

- **多数据源容错**：A股/ETF 用「东方财富 → 新浪」(它们的 `""` 才是真·不复权)；港股/美股用「东方财富 → 新浪 → Yahoo」兜底。A股搜索改用轻量代码表，更快且不易超时。
- **为何 A股/ETF 不接 Yahoo**：Yahoo 即使 `auto_adjust=False`，也会对拆股/转增/配股做还原(如招商银行 2005 显示 ~3.98 而非真实 ~8)，会让按真实成交价计算的手数与收益失真；腾讯 `stock_zh_a_hist_tx` 的「不复权」同样实为前复权。两者均不用于 A股取数。
- **国外数据源 Yahoo Finance**：通过 `yfinance` 接入，覆盖 A股/港股/美股/ETF，并能补齐港股/美股的分红。境内直连可能较慢，建议有外网/VPN 时使用：
  ```bash
  PREFER_YFINANCE=1 ./start.sh      # 让 Yahoo 优先
  ```
- **接口限流**：短时间内大量请求可能被数据源临时限流（表现为连接被重置）。已内置指数退避重试，仍失败时请稍候重试，并尽量直接输入精确代码而非频繁模糊搜索。
- **港股每手股数**无统一接口，默认按 100 股/手计算，可在表单「每手股数」手动修改。
- **A股分红/送转**来自东方财富分红明细，较为可靠。
- **美股/港股/ETF 分红明细**在数据源较弱：复投收益与年化仍由后复权价保证；
  「分红金额」与「不复投」结果在缺失明细时为估算值，并在页面顶部以 warning 标注。

## 本地缓存

首次查询某标的会从数据源拉取并写入 `backend/data/dca_cache.sqlite`（含
`instruments / price_history / dividends / fetch_log` 四张表）；后续相同或被覆盖区间的查询
直接读本地库，毫秒级返回。删除该文件即可清空缓存。

## 免责声明

本项目数据来自 akshare，仅供学习与研究参考，不构成任何投资建议。
