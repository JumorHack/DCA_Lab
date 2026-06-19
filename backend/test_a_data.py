"""A股数据获取自检脚本。

依次测试多个数据源(腾讯/东方财富/新浪)、应用取数管线(自动兜底+本地缓存)、
分红、以及一次完整回测，帮助快速定位「能不能拿到数据」。

用法:
    cd backend
    ./.venv/bin/python test_a_data.py            # 默认测试 600519(贵州茅台)
    ./.venv/bin/python test_a_data.py 000001     # 指定代码
"""
import os
import sys
import time
import datetime as dt

# 让脚本无论从哪个目录运行都能 import 到 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入应用数据层(导入时会自动剔除泄漏的本地代理，与后端运行时行为一致)
from app.services import data  # noqa: E402
from app.services import engine  # noqa: E402
import akshare as ak  # noqa: E402

CODE = sys.argv[1] if len(sys.argv) > 1 else "600519"
END = dt.date.today()
START = END - dt.timedelta(days=180)
sd, ed = START.strftime("%Y%m%d"), END.strftime("%Y%m%d")
sd_iso, ed_iso = START.isoformat(), END.isoformat()


def line():
    print("-" * 64)


def show_proxy():
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    cur = {k: os.environ[k] for k in keys if os.environ.get(k)}
    print("当前进程代理:", cur or "(已无，直连)")


print(f"测试 A 股: {CODE}    区间: {sd_iso} ~ {ed_iso}")
show_proxy()

tx_ok = em_ok = sina_ok = yf_ok = hist_ok = False

line()
print("[1] 腾讯      ak.stock_zh_a_hist_tx ... (注: 其不复权实为前复权, 已不用于取数, 仅测连通)")
try:
    sym = data._sina_a_symbol(CODE)
    t = time.time()
    df = ak.stock_zh_a_hist_tx(symbol=sym, start_date=sd, end_date=ed, adjust="")
    print(f"  OK   symbol={sym}, {len(df)} 行, 耗时 {time.time() - t:.1f}s")
    tx_ok = len(df) > 0
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:170]}")

line()
print("[2] 东方财富  ak.stock_zh_a_hist ...")
try:
    t = time.time()
    df = ak.stock_zh_a_hist(symbol=CODE, period="daily", start_date=sd, end_date=ed, adjust="")
    last = df.tail(1)[["日期", "收盘"]].to_dict("records") if len(df) else []
    print(f"  OK   {len(df)} 行, 耗时 {time.time() - t:.1f}s, 最新: {last}")
    em_ok = len(df) > 0
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:170]}")

line()
print("[3] 新浪      ak.stock_zh_a_daily ...")
try:
    sym = data._sina_a_symbol(CODE)
    t = time.time()
    df = ak.stock_zh_a_daily(symbol=sym, start_date=sd, end_date=ed, adjust="")
    print(f"  OK   symbol={sym}, {len(df)} 行, 耗时 {time.time() - t:.1f}s")
    sina_ok = len(df) > 0
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:170]}")

line()
print("[4] Yahoo     yfinance (国外源, 需可访问 Yahoo/科学上网) ...")
try:
    import yfinance as yf  # type: ignore[import]
    yf_sym = data._yf_symbol("a", CODE, None)
    t = time.time()
    h = yf.Ticker(yf_sym).history(start=sd_iso, end=ed_iso, auto_adjust=False, actions=False)
    print(f"  OK   symbol={yf_sym}, {len(h)} 行, 耗时 {time.time() - t:.1f}s")
    yf_ok = len(h) > 0
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:170]}")

line()
print("[5] 应用管线  data.get_history (腾讯->东财->新浪->Yahoo 兜底 + 本地缓存) ...")
try:
    t = time.time()
    h = data.get_history("a", CODE, sd_iso, ed_iso)
    print(f"  OK   {len(h)} 行, 首次耗时 {time.time() - t:.1f}s, 列: {list(h.columns)}")
    if len(h):
        print("  最新:", h.tail(1).to_dict("records"))
    t = time.time()
    data.get_history("a", CODE, sd_iso, ed_iso)
    print(f"  二次(命中本地缓存) 耗时 {time.time() - t:.3f}s")
    hist_ok = len(h) > 0
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:200]}")

line()
print("[6] 分红      data.get_dividends ...")
try:
    divs = data.get_dividends("a", CODE, "2000-01-01", ed_iso)
    print(f"  OK   共 {len(divs)} 条分红/送转记录")
    for d in divs[-3:]:
        print("    ", d)
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:170]}")

line()
print("[7] 完整回测  engine.run_backtest (每月 5000 元, 复投) ...")
try:
    r = engine.run_backtest("a", CODE, START.strftime("%Y-%m"), END.strftime("%Y-%m"),
                            "amount", 5000, "reinvest")
    s = r["summary"]
    print(f"  OK   本金={s['principal']} 现值={s['current_value']} "
          f"分红={s['dividend_total']} 年化={s['annualized']}")
    if r["warnings"]:
        print("  warnings:", "; ".join(r["warnings"]))
except Exception as e:
    print(f"  失败: {type(e).__name__}: {str(e)[:200]}")

line()
print("结论:")
print(f"  腾讯直连       : {'✅ 可用' if tx_ok else '❌ 不可用'}")
print(f"  东方财富直连   : {'✅ 可用' if em_ok else '❌ 不可用'}")
print(f"  新浪直连       : {'✅ 可用' if sina_ok else '❌ 不可用'}")
print(f"  Yahoo(国外源)  : {'✅ 可用' if yf_ok else '❌ 不可用'}")
print(f"  应用取数管线   : {'✅ 可用' if hist_ok else '❌ 不可用'}")
if not (tx_ok or em_ok or sina_ok or yf_ok):
    print("  → 所有数据源都连不上：多为网络/VPN 问题(或同时被限流)，请检查网络后重试。")
elif hist_ok:
    print("  → 数据获取正常，网页端可正常回测。")
else:
    print("  → 有可用数据源但管线异常，请把以上报错发给开发者。")
