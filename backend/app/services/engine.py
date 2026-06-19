"""Monthly dollar-cost-averaging (定投) simulation engine.

Design notes
------------
* Buys use the **unadjusted (raw)** close so share counts and lot logic reflect
  real money.
* The dividend-reinvested holding value is computed with the robust closed form
  ``Σ costᵢ × P_hfq(end)/P_hfq(tᵢ)`` (后复权), which automatically embeds splits
  and reinvested dividends and works uniformly across markets.
* Explicit dividend / 送转 records (reliable for A股) drive the displayed dividend
  amount and the non-reinvest cash bucket. Where records are missing we fall back
  to an estimate derived from the 后复权 vs 不复权 gap and emit a warning.
* Annualized return uses XIRR (money-weighted), appropriate for periodic投入.
"""
from __future__ import annotations

import bisect
import math
import datetime as dt
from typing import Optional, Dict, Any, List

from ..markets import get_market
from .data import get_history, get_dividends, resolve_instrument
from .xirr import xirr


def _parse_month(s: str):
    y, m = s.split("-")[:2]
    return int(y), int(m)


def _last_day_of_month(y: int, m: int) -> dt.date:
    if m == 12:
        return dt.date(y, 12, 31)
    return dt.date(y, m + 1, 1) - dt.timedelta(days=1)


def _month_iter(y0: int, m0: int, y1: int, m1: int):
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _r(v, n=2):
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return None


def run_backtest(
    market: str,
    code: str,
    start: str,
    end: str,
    strategy_type: str,
    strategy_value: float,
    dividend_mode: str,
    invest_day: int = 1,
    lot_override: Optional[int] = None,
) -> Dict[str, Any]:
    cfg = get_market(market)
    inst = resolve_instrument(market, code)
    lot = int(lot_override) if lot_override else int(inst.get("lot") or cfg.default_lot)
    lot = max(lot, 1)
    currency = inst.get("currency") or cfg.currency
    resolved_code = inst["code"]
    ak_symbol = inst.get("ak_symbol")
    reinvest = dividend_mode == "reinvest"

    if strategy_value is None or float(strategy_value) <= 0:
        raise ValueError("定投数值需大于 0")

    sy, sm = _parse_month(start)
    ey, em = _parse_month(end)
    start_date = dt.date(sy, sm, 1)
    end_date = min(_last_day_of_month(ey, em), dt.date.today())
    if start_date > end_date:
        raise ValueError("开始时间需早于结束时间")

    price_df = get_history(market, resolved_code, start_date.isoformat(), end_date.isoformat(), ak_symbol)
    if price_df is None or price_df.empty:
        raise ValueError("未获取到该标的的历史行情, 请检查市场与代码是否正确")

    prices = []
    for rec in price_df.to_dict("records"):
        raw = rec.get("close_raw")
        if raw is None or raw <= 0:
            continue
        hfq = rec.get("close_hfq")
        if hfq is None or hfq <= 0:
            hfq = raw
        prices.append((dt.date.fromisoformat(rec["date"]), float(raw), float(hfq)))
    prices.sort(key=lambda x: x[0])
    if not prices:
        raise ValueError("历史行情为空")
    dates = [p[0] for p in prices]

    def price_on_or_after(target: dt.date):
        i = bisect.bisect_left(dates, target)
        return prices[i] if i < len(dates) else None

    def price_on_or_before(target: dt.date):
        i = bisect.bisect_right(dates, target) - 1
        return prices[i] if i >= 0 else None

    warnings: List[str] = []

    # ---- monthly buy schedule -------------------------------------------- #
    buy_events = []
    day = min(max(int(invest_day or 1), 1), 28)
    for (y, m) in _month_iter(sy, sm, ey, em):
        p = price_on_or_after(dt.date(y, m, day))
        if p is None or p[0].year != y or p[0].month != m:
            continue
        buy_events.append(p)
    if not buy_events:
        raise ValueError("所选区间内没有可交易的定投日")

    # ---- dividend / 送转 events ------------------------------------------ #
    div_rows = get_dividends(market, resolved_code, start_date.isoformat(), end_date.isoformat(), ak_symbol)
    div_events = []
    for r in div_rows:
        try:
            ed = dt.date.fromisoformat(r["ex_date"])
        except (TypeError, ValueError):
            continue
        if start_date <= ed <= end_date:
            div_events.append(
                {
                    "date": ed,
                    "cash": float(r.get("cash_per_share") or 0.0),
                    "bonus": float(r.get("bonus_ratio") or 0.0),
                    "split": float(r.get("split_factor") or 1.0) or 1.0,
                }
            )

    # ---- merged chronological event loop --------------------------------- #
    events = [(bd, 1, {"raw": braw, "hfq": bhfq}) for (bd, braw, bhfq) in buy_events]
    events += [(dv["date"], 0, dv) for dv in div_events]
    events.sort(key=lambda e: (e[0], e[1]))  # dividend (0) before buy (1) on same day

    shares = 0.0
    principal = 0.0
    leftover = 0.0
    div_cash = 0.0
    div_gross = 0.0
    hfq_units = 0.0           # Σ costᵢ / P_hfq(tᵢ)
    raw_units = 0.0           # Σ costᵢ / P_raw(tᵢ)  (price-only baseline)
    transactions: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []

    for (edate, etype, payload) in events:
        if etype == 0:  # dividend / corporate action
            if shares <= 0:
                continue
            if payload["split"] and payload["split"] != 1.0:
                shares *= payload["split"]
            if payload["bonus"]:
                shares *= (1.0 + payload["bonus"])
            if payload["cash"]:
                gross = shares * payload["cash"]
                div_gross += gross
                if reinvest:
                    pa = price_on_or_after(edate)
                    if pa and pa[1] > 0:
                        shares += gross / pa[1]
                else:
                    div_cash += gross
            continue

        # buy
        braw, bhfq = payload["raw"], payload["hfq"]
        if strategy_type == "amount":
            avail = leftover + float(strategy_value)
            lots = math.floor(avail / (lot * braw)) if braw > 0 else 0
            qty = lots * lot
            cost = qty * braw
            leftover = avail - cost
            principal += float(strategy_value)
        else:  # fixed share count
            qty = float(strategy_value)
            cost = qty * braw
            principal += cost

        if qty > 0:
            shares += qty
            if bhfq > 0:
                hfq_units += cost / bhfq
            if braw > 0:
                raw_units += cost / braw

        transactions.append(
            {
                "date": edate.isoformat(),
                "price": _r(braw, 4),
                "shares": _r(qty, 4),
                "cost": _r(cost, 2),
                "leftover": _r(leftover, 2),
            }
        )
        value_now = (hfq_units * bhfq if reinvest else shares * braw + div_cash) + leftover
        timeline.append(
            {
                "date": edate.isoformat(),
                "invested": _r(principal),
                "value": _r(value_now),
                "dividend": _r(div_gross),
            }
        )

    # ---- end valuation --------------------------------------------------- #
    end_row = price_on_or_before(end_date) or prices[-1]
    end_date_actual, raw_end, hfq_end = end_row
    reinvest_holding = hfq_units * hfq_end
    price_only_holding = raw_units * raw_end
    estimated_dividend = max(reinvest_holding - price_only_holding, 0.0)

    if reinvest:
        holding_value = reinvest_holding
        current_value = holding_value + leftover
        sim_holding = shares * raw_end
        if reinvest_holding > 0 and abs(sim_holding - reinvest_holding) / reinvest_holding > 0.05:
            warnings.append("复投显式模拟与后复权闭式存在偏差(可能为分红/拆送数据缺失), 当前价值以后复权口径为准。")
        if div_gross > 0:
            dividend_total = div_gross
        else:
            dividend_total = estimated_dividend
            if dividend_total > 0:
                warnings.append("未获取到分红明细, 分红金额为按后复权估算值(含再投资增值)。")
        shares_held = reinvest_holding / raw_end if raw_end > 0 else shares
    else:
        holding_value = shares * raw_end
        if div_gross > 0:
            dividend_total = div_gross
            current_value = holding_value + div_cash + leftover
        else:
            dividend_total = estimated_dividend
            current_value = holding_value + estimated_dividend + leftover
            if estimated_dividend > 0:
                warnings.append("未获取到分红明细, 分红金额为估算值并按现金计入当前价值。")
        shares_held = shares

    if cfg.lot_is_uncertain and not lot_override:
        warnings.append("港股每手股数无统一接口, 已默认按 100 股/手计算, 可在表单中手动修改。")

    total_bought = sum((t.get("shares") or 0.0) for t in transactions)
    if strategy_type == "amount" and total_bought <= 0:
        lot_cost = lot * (buy_events[0][1] if buy_events else 0.0)
        warnings.append(
            f"每月金额不足以买入 1 手(约需 {lot_cost:,.0f} {currency})，"
            f"全程未能买入、资金以现金留存、收益≈0；请增大每月金额或改用「按股数」。"
        )

    total_return_pct = (current_value - principal) / principal if principal > 0 else None

    # ---- XIRR ------------------------------------------------------------ #
    cashflows = []
    if strategy_type == "amount":
        for (bd, _, _) in buy_events:
            cashflows.append((bd, -float(strategy_value)))
    else:
        for tr in transactions:
            cashflows.append((dt.date.fromisoformat(tr["date"]), -float(tr["cost"] or 0.0)))
    cashflows.append((end_date_actual, float(current_value)))
    annualized = xirr(cashflows)

    final_point = {
        "date": end_date_actual.isoformat(),
        "invested": _r(principal),
        "value": _r(current_value),
        "dividend": _r(dividend_total),
    }
    if timeline and timeline[-1]["date"] == final_point["date"]:
        timeline[-1] = final_point
    else:
        timeline.append(final_point)

    return {
        "summary": {
            "market": market,
            "code": resolved_code,
            "name": inst.get("name") or resolved_code,
            "currency": currency,
            "lot": lot,
            "dividend_mode": dividend_mode,
            "strategy_type": strategy_type,
            "strategy_value": float(strategy_value),
            "start": start,
            "end": end,
            "end_date": end_date_actual.isoformat(),
            "months": len(buy_events),
            "principal": _r(principal),
            "current_value": _r(current_value),
            "dividend_total": _r(dividend_total),
            "leftover_cash": _r(leftover),
            "shares_held": _r(shares_held, 4),
            "end_price": _r(raw_end, 4),
            "total_return_pct": total_return_pct,
            "annualized": annualized,
            "dividend_estimated": div_gross <= 0 and estimated_dividend > 0,
        },
        "timeline": timeline,
        "transactions": transactions,
        "warnings": warnings,
    }
