"""akshare data access with a "DB-first" caching policy.

For every dataset we first look in the local SQLite cache; akshare is only
called when the cache is missing or stale, and any fetched data is written back
so subsequent queries are served from disk in milliseconds.
"""
from __future__ import annotations

import os
import sys
import time
import datetime as dt
import urllib.request as _urllib_request
from typing import Optional, List, Dict, Any, Callable


def _neutralize_leaked_local_proxy() -> None:
    """Drop a leaked *local* proxy so akshare can reach the (domestic) data source.

    Some IDE/sandbox shells (e.g. Cursor) inject ``HTTP_PROXY=http://127.0.0.1:566xx``
    which is only valid inside that sandbox. When it leaks into the backend process,
    ``requests`` (used by akshare) routes every call through it and fails with
    ``ProxyError`` -> HTTP 502. We remove such a local proxy coming from either
    environment variables *or* the macOS system network settings (which ``requests``
    reads via ``urllib.getproxies``). Non-local proxies are left untouched.
    """
    local_markers = ("127.0.0.1", "localhost", "::1")

    for key in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
        "SOCKS_PROXY", "SOCKS5_PROXY", "socks_proxy", "socks5_proxy",
    ):
        val = os.environ.get(key, "")
        if val and any(m in val for m in local_markers):
            os.environ.pop(key, None)

    try:
        detected = _urllib_request.getproxies()
    except Exception:
        detected = {}
    if any(any(m in str(v) for m in local_markers) for v in detected.values()):
        no_proxy = lambda: {}  # noqa: E731
        _urllib_request.getproxies = no_proxy  # type: ignore[assignment]
        for mod_name in ("requests.compat", "requests.utils"):
            try:
                __import__(mod_name)
                setattr(sys.modules[mod_name], "getproxies", no_proxy)
            except Exception:
                pass


_neutralize_leaked_local_proxy()

import akshare as ak  # noqa: E402
import pandas as pd  # noqa: E402

from .. import db  # noqa: E402
from ..markets import get_market  # noqa: E402

INSTRUMENTS_TTL_HOURS = 24
DIVIDENDS_TTL_HOURS = 24
_RETRY_ATTEMPTS = 5
_RETRY_BASE_DELAY = 1.0


def _retry(func: Callable, attempts: int = _RETRY_ATTEMPTS, base_delay: float = _RETRY_BASE_DELAY):
    """Retry a flaky network call. akshare's eastmoney endpoints intermittently
    reset connections ("RemoteDisconnected"); exponential backoff usually recovers."""
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            return func()
        except Exception as e:  # noqa: BLE001 - akshare raises a variety of errors
            last_err = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))  # 1, 2, 4, 8s
    raise last_err  # type: ignore[misc]

_RENAME = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
}


# --------------------------------------------------------------------------- #
# small date helpers
# --------------------------------------------------------------------------- #
def today_iso() -> str:
    return dt.date.today().isoformat()


def _to_ymd(iso: str) -> str:
    return iso.replace("-", "")


def _iso(d: dt.date) -> str:
    return d.isoformat()


def _parse_iso(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _prev_day(iso: str) -> str:
    return _iso(_parse_iso(iso) - dt.timedelta(days=1))


def _next_day(iso: str) -> str:
    return _iso(_parse_iso(iso) + dt.timedelta(days=1))


def _hours_since(ts: Optional[str]) -> float:
    if not ts:
        return 1e9
    try:
        then = dt.datetime.fromisoformat(ts)
    except ValueError:
        return 1e9
    return (dt.datetime.now() - then).total_seconds() / 3600.0


# --------------------------------------------------------------------------- #
# history (raw + hfq)
# --------------------------------------------------------------------------- #
def _normalize_any(df) -> Optional[pd.DataFrame]:
    """Normalize an akshare OHLCV frame from either eastmoney (Chinese columns,
    date column) or sina (english columns, date column or index) into
    [date, open, close, high, low, volume]."""
    if df is None or len(df) == 0:
        return None
    df = df.copy()
    cols = {str(c).strip().lower(): c for c in df.columns}
    if not any(k in cols for k in ("date", "日期")):
        df = df.reset_index()
        cols = {str(c).strip().lower(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    dcol = pick("date", "日期")
    if dcol is None:
        return None
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[dcol]).dt.strftime("%Y-%m-%d")
    for std, aliases in (
        ("open", ("open", "开盘")),
        ("close", ("close", "收盘")),
        ("high", ("high", "最高")),
        ("low", ("low", "最低")),
        ("volume", ("volume", "成交量")),
    ):
        col = pick(*aliases)
        if col is not None:
            out[std] = pd.to_numeric(df[col], errors="coerce")
    return out


def _sina_a_symbol(code: str) -> str:
    """A股代码 -> 新浪带市场前缀代码 (sh/sz/bj)."""
    c = code.strip()
    if c[:3] in ("600", "601", "603", "605", "688", "689", "900") or c[:2] in ("51", "11"):
        return "sh" + c
    if c[:3] in ("000", "001", "002", "003", "300", "301", "200", "159") or c[:2] == "12":
        return "sz" + c
    if c[:2] in ("43", "83", "87", "88", "92") or c[:1] in ("4", "8"):
        return "bj" + c
    return ("sh" if c.startswith("6") else "sz") + c


def _sina_etf_symbol(code: str) -> str:
    c = code.strip()
    return ("sh" if c.startswith("5") else "sz") + c


def _yf_symbol(market: str, code: str, ak_symbol: Optional[str]) -> str:
    """Map an instrument to its Yahoo Finance ticker."""
    if market == "us":
        if ak_symbol and "." in ak_symbol:
            return ak_symbol.split(".", 1)[1]  # 105.AAPL -> AAPL
        return code
    if market == "hk":
        digits = "".join(ch for ch in code if ch.isdigit())
        if digits:
            return f"{int(digits):04d}.HK"  # 00700 -> 0700.HK
        return code
    pref = (_sina_a_symbol(code) if market == "a" else _sina_etf_symbol(code))[:2]
    return code + {"sh": ".SS", "sz": ".SZ", "bj": ".BJ"}.get(pref, ".SS")


def _hist_call(source: str, market: str, code: str, ak_symbol: Optional[str],
               start_ymd: str, end_ymd: str, adjust: str):
    if source == "eastmoney":
        if market == "a":
            return ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_ymd, end_date=end_ymd, adjust=adjust)
        if market == "hk":
            return ak.stock_hk_hist(symbol=code, period="daily", start_date=start_ymd, end_date=end_ymd, adjust=adjust)
        if market == "us":
            return ak.stock_us_hist(symbol=ak_symbol or code, period="daily", start_date=start_ymd, end_date=end_ymd, adjust=adjust)
        if market == "etf":
            return ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_ymd, end_date=end_ymd, adjust=adjust)
    elif source == "yfinance":
        # 国外开放数据源 Yahoo Finance, 覆盖 A股/港股/美股/ETF。
        import yfinance as yf
        sym = _yf_symbol(market, code, ak_symbol)
        auto = adjust in ("hfq", "qfq")  # 复权价 -> auto_adjust=True
        start_d = f"{start_ymd[:4]}-{start_ymd[4:6]}-{start_ymd[6:]}"
        end_d = _next_day(f"{end_ymd[:4]}-{end_ymd[4:6]}-{end_ymd[6:]}")  # yfinance end 为开区间
        h = yf.Ticker(sym).history(start=start_d, end=end_d, auto_adjust=auto, actions=False)
        if h is None or len(h) == 0:
            return None
        return h.reset_index()
    elif source == "sina":
        if market == "a":
            return ak.stock_zh_a_daily(symbol=_sina_a_symbol(code), start_date=start_ymd, end_date=end_ymd, adjust=adjust)
        if market == "hk":
            return ak.stock_hk_daily(symbol=code, adjust=adjust)
        if market == "us":
            if adjust == "hfq":
                raise ValueError("sina-us-no-hfq")  # fall back to qfq (same ratio)
            return ak.stock_us_daily(symbol=code, adjust=adjust)
        if market == "etf":
            if adjust:
                raise ValueError("sina-etf-no-adjust")  # only unadjusted available
            return ak.fund_etf_hist_sina(symbol=_sina_etf_symbol(code))
    raise ValueError(f"未知数据源/市场: {source}/{market}")


def _fetch_one(source: str, market: str, code: str, ak_symbol: Optional[str],
               start_iso: str, end_iso: str) -> Optional[pd.DataFrame]:
    start_ymd, end_ymd = _to_ymd(start_iso), _to_ymd(end_iso)
    raw_n = _normalize_any(_hist_call(source, market, code, ak_symbol, start_ymd, end_ymd, ""))
    if raw_n is None or raw_n.empty or "close" not in raw_n.columns:
        return None
    raw_n = raw_n.rename(columns={"close": "close_raw"})

    adj_n = None
    for adjust in ("hfq", "qfq"):  # qfq/hfq give the same end/start ratio
        try:
            adj = _normalize_any(_hist_call(source, market, code, ak_symbol, start_ymd, end_ymd, adjust))
            if adj is not None and not adj.empty and "close" in adj.columns:
                adj_n = adj[["date", "close"]].rename(columns={"close": "close_hfq"})
                break
        except Exception:
            continue

    if adj_n is None:
        merged = raw_n.copy()
        merged["close_hfq"] = merged["close_raw"]
    else:
        merged = raw_n.merge(adj_n, on="date", how="left")
        merged["close_hfq"] = merged["close_hfq"].fillna(merged["close_raw"])

    # sina endpoints return the full history -> clip to the requested window.
    merged = merged[(merged["date"] >= start_iso) & (merged["date"] <= end_iso)]
    return merged


def _fetch_history(market: str, code: str, ak_symbol: Optional[str], start_iso: str, end_iso: str) -> pd.DataFrame:
    """Fetch raw + 后复权 closes from multiple providers with fallback.
    默认境内源优先(腾讯/东财/新浪), Yahoo(yfinance) 作为兜底; 设置环境变量
    PREFER_YFINANCE=1 可让 Yahoo 优先(适合有外网/VPN 的环境)。"""
    # 不使用腾讯 stock_zh_a_hist_tx —— 其 adjust="" 实为「前复权」。
    # A股/ETF 的真·不复权只可靠地来自东财/新浪; Yahoo 即使 auto_adjust=False 也会对
    # 拆股/转增/配股做还原(历史价偏低, 如招行 2005 显示 ~3.98 而非真实 ~8),
    # 会使按真实成交价的手数/收益失真, 故 A股/ETF 不接 Yahoo, 仅在港股/美股兜底。
    if market in ("a", "etf"):
        sources = ["eastmoney", "sina"]
    else:  # hk / us
        sources = ["eastmoney", "sina", "yfinance"]
    if os.environ.get("PREFER_YFINANCE", "").strip().lower() in ("1", "true", "yes") and "yfinance" in sources:
        sources = ["yfinance"] + [s for s in sources if s != "yfinance"]
    last_err: Optional[Exception] = None
    for source in sources:
        try:
            df = _retry(
                lambda s=source: _fetch_one(s, market, code, ak_symbol, start_iso, end_iso),
                attempts=2,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return pd.DataFrame()


def get_history(market: str, code: str, start_iso: str, end_iso: str, ak_symbol: Optional[str] = None) -> pd.DataFrame:
    """Return cached daily history for [start, end]; fetch only missing ranges."""
    eff_end = min(end_iso, today_iso())
    log = db.get_fetch_log(market, code, "price")

    ranges: List[tuple] = []
    if not log or not log.get("range_start"):
        ranges.append((start_iso, eff_end))
    else:
        have_start, have_end = log["range_start"], log["range_end"]
        if start_iso < have_start:
            ranges.append((start_iso, _prev_day(have_start)))
        if eff_end > have_end:
            ranges.append((_next_day(have_end), eff_end))

    fetched_any = False
    for s, e in ranges:
        if s > e:
            continue
        df = _fetch_history(market, code, ak_symbol, s, e)
        if df is not None and not df.empty:
            db.upsert_price_history(market, code, df)
            fetched_any = True

    if fetched_any or not log:
        new_start = start_iso
        new_end = eff_end
        if log and log.get("range_start"):
            new_start = min(start_iso, log["range_start"])
            new_end = max(eff_end, log["range_end"])
        db.set_fetch_log(market, code, "price", new_start, new_end)

    return db.read_price_history(market, code, start_iso, end_iso)


# --------------------------------------------------------------------------- #
# dividends
# --------------------------------------------------------------------------- #
def _safe_float(v) -> float:
    try:
        f = float(str(v).replace(",", "").strip())
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0


def _fetch_dividends_a(code: str) -> List[Dict[str, Any]]:
    """东方财富-分红配送明细: 现金分红/送转 按每 10 股计."""
    df = _retry(lambda: ak.stock_fhps_detail_em(symbol=code))
    rows: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return rows
    ex_col = next((c for c in df.columns if "除权除息日" in c), None)
    cash_col = next(
        (c for c in df.columns if "现金分红" in c and "比例" in c and "描述" not in c), None
    )
    bonus_col = next((c for c in df.columns if "送转" in c and "总" in c), None)
    if ex_col is None:
        return rows
    for _, r in df.iterrows():
        ex = r.get(ex_col)
        if ex is None or pd.isna(ex):
            continue
        try:
            ex_iso = pd.to_datetime(ex).strftime("%Y-%m-%d")
        except Exception:
            continue
        cash10 = _safe_float(r.get(cash_col)) if cash_col else 0.0
        bonus10 = _safe_float(r.get(bonus_col)) if bonus_col else 0.0
        if cash10 == 0.0 and bonus10 == 0.0:
            continue
        rows.append(
            {
                "ex_date": ex_iso,
                "cash_per_share": cash10 / 10.0,
                "bonus_ratio": bonus10 / 10.0,
                "split_factor": 1.0,
            }
        )
    return rows


def _fetch_dividends_yf(market: str, code: str, ak_symbol: Optional[str]) -> List[Dict[str, Any]]:
    """用 Yahoo Finance 取现金分红 + 拆股(港股/美股/ETF 的主要分红来源)。"""
    import yfinance as yf

    sym = _yf_symbol(market, code, ak_symbol)
    tk = yf.Ticker(sym)
    by_date: Dict[str, Dict[str, Any]] = {}

    def _rec(iso: str) -> Dict[str, Any]:
        return by_date.setdefault(
            iso, {"ex_date": iso, "cash_per_share": 0.0, "bonus_ratio": 0.0, "split_factor": 1.0}
        )

    try:
        for d, v in tk.dividends.items():
            if v:
                _rec(pd.Timestamp(d).strftime("%Y-%m-%d"))["cash_per_share"] += float(v)
    except Exception:
        pass
    try:
        for d, v in tk.splits.items():
            if v:
                _rec(pd.Timestamp(d).strftime("%Y-%m-%d"))["split_factor"] *= float(v)
    except Exception:
        pass
    return list(by_date.values())


def _fetch_dividends(market: str, code: str, ak_symbol: Optional[str]) -> List[Dict[str, Any]]:
    if market == "a":
        rows = _fetch_dividends_a(code)
        if rows:
            return rows
        try:  # A股兜底也可用 Yahoo(需可访问)
            return _fetch_dividends_yf(market, code, ak_symbol)
        except Exception:
            return rows
    # 港股 / 美股 / ETF: 优先用 Yahoo 取分红, 失败则退回空(复投收益仍由后复权价保证)。
    try:
        return _fetch_dividends_yf(market, code, ak_symbol)
    except Exception:
        return []


def get_dividends(market: str, code: str, start_iso: str, end_iso: str, ak_symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    log = db.get_fetch_log(market, code, "dividends")
    fresh = log is not None and _hours_since(log.get("fetched_at")) < DIVIDENDS_TTL_HOURS
    if not fresh:
        try:
            rows = _fetch_dividends(market, code, ak_symbol)
            for r in rows:
                r.update({"market": market, "code": code, "raw": None})
            db.replace_dividends(market, code, rows)
        except Exception:
            pass
        db.set_fetch_log(market, code, "dividends")
    return db.read_dividends(market, code, start_iso, end_iso)


# --------------------------------------------------------------------------- #
# instruments / search
# --------------------------------------------------------------------------- #
def _fetch_spot(market: str) -> List[Dict[str, Any]]:
    cfg = get_market(market)
    rows: List[Dict[str, Any]] = []
    if market == "a":
        # 轻量清单(仅代码+名称), 比下载全市场实时行情快很多; 新浪实时行情兜底。
        try:
            df = _retry(ak.stock_info_a_code_name, attempts=2)
        except Exception:
            df = _retry(ak.stock_zh_a_spot, attempts=2)
        code_col = next((c for c in ("code", "代码") if c in df.columns), df.columns[0])
        name_col = next((c for c in ("name", "名称") if c in df.columns), df.columns[1])
        for _, r in df.iterrows():
            digits = "".join(ch for ch in str(r[code_col]) if ch.isdigit())
            code = digits[-6:] if len(digits) >= 6 else str(r[code_col]).strip()
            if len(code) != 6:
                continue
            rows.append({"market": "a", "code": code, "name": str(r[name_col]).strip(),
                         "lot": cfg.default_lot, "currency": cfg.currency, "ak_symbol": code})
    elif market == "hk":
        df = _retry(ak.stock_hk_spot_em)
        for _, r in df.iterrows():
            code = str(r["代码"]).strip()
            rows.append({"market": "hk", "code": code, "name": str(r["名称"]).strip(),
                         "lot": cfg.default_lot, "currency": cfg.currency, "ak_symbol": code})
    elif market == "us":
        df = _retry(ak.stock_us_spot_em)
        for _, r in df.iterrows():
            ak_symbol = str(r["代码"]).strip()  # e.g. 105.AAPL
            ticker = ak_symbol.split(".", 1)[1] if "." in ak_symbol else ak_symbol
            rows.append({"market": "us", "code": ticker, "name": str(r["名称"]).strip(),
                         "lot": cfg.default_lot, "currency": cfg.currency, "ak_symbol": ak_symbol})
    elif market == "etf":
        df = _retry(ak.fund_etf_spot_em)
        code_col = "代码" if "代码" in df.columns else df.columns[0]
        name_col = "名称" if "名称" in df.columns else df.columns[1]
        for _, r in df.iterrows():
            code = str(r[code_col]).strip()
            rows.append({"market": "etf", "code": code, "name": str(r[name_col]).strip(),
                         "lot": cfg.default_lot, "currency": cfg.currency, "ak_symbol": code})
    return rows


def ensure_instruments(market: str) -> None:
    get_market(market)
    log = db.get_fetch_log(market, "_ALL_", "instruments")
    fresh = (
        log is not None
        and _hours_since(log.get("fetched_at")) < INSTRUMENTS_TTL_HOURS
        and db.count_instruments(market) > 0
    )
    if fresh:
        return
    rows = _fetch_spot(market)
    if rows:
        db.upsert_instruments(rows)
        db.set_fetch_log(market, "_ALL_", "instruments")


def search(market: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    ensure_instruments(market)
    return db.search_instruments(market, query.strip(), limit)


def _resolve_by_name(market: str, name: str) -> Optional[Dict[str, Any]]:
    """按名称模糊匹配出最匹配的一个标的(优先精确同名)。"""
    matches = search(market, name, 20)
    if not matches:
        return None
    exact = [m for m in matches if (m.get("name") or "") == name]
    return exact[0] if exact else matches[0]


def resolve_instrument(market: str, code: str) -> Dict[str, Any]:
    """把用户输入的「代码或名称」解析成完整标的记录。

    纯数字代码直接使用; 中文名称/英文名会通过搜索解析为真实代码; 都解析不到时
    抛出明确的 ValueError(而不是让 akshare 拿着名称去请求最后报晦涩的网络错误)。
    """
    cfg = get_market(market)
    code = code.strip()
    if not code:
        raise ValueError("请输入股票/ETF 代码或名称")

    if market == "us":
        if "." in code and code.split(".", 1)[0].isdigit():  # 105.AAPL
            found = db.find_instrument_by_ak_symbol(market, code)
            if found:
                return found
            ticker = code.split(".", 1)[1]
            return {"market": market, "code": ticker, "name": ticker, "lot": cfg.default_lot,
                    "currency": cfg.currency, "ak_symbol": code}
        ticker = code.upper()
        found = db.get_instrument(market, ticker) or db.find_instrument_by_ak_symbol(market, code)
        if found:
            return found
        ensure_instruments(market)
        found = db.get_instrument(market, ticker) or db.find_instrument_by_ak_symbol(market, code)
        if found:
            return found
        resolved = _resolve_by_name(market, code)
        if resolved:
            return resolved
        if all(ord(c) < 128 for c in ticker) and ticker.replace(".", "").replace("-", "").isalnum():
            return {"market": market, "code": ticker, "name": ticker, "lot": cfg.default_lot,
                    "currency": cfg.currency, "ak_symbol": ticker}
        raise ValueError(f"未找到美股「{code}」，请输入正确代码(如 AAPL)或从下拉中选择")

    # A股 / 港股 / ETF
    if market == "hk" and code.isdigit():
        code = code.zfill(5)
    found = db.get_instrument(market, code)
    if found:
        return found
    if code.isdigit():  # 纯数字代码, 直接用(名称可能未缓存)
        return {"market": market, "code": code, "name": code, "lot": cfg.default_lot,
                "currency": cfg.currency, "ak_symbol": code}
    resolved = _resolve_by_name(market, code)  # 当作名称解析
    if resolved:
        return resolved
    raise ValueError(f"未找到「{code}」对应的标的，请输入正确代码(如 600036)或从下拉中选择")
