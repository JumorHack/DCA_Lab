"""Money-weighted annualized return (XIRR) for irregular cash flows."""
from __future__ import annotations

import datetime as dt
from typing import List, Tuple, Optional

CashFlow = Tuple[dt.date, float]


def _npv(rate: float, years: List[float], amounts: List[float]) -> float:
    return sum(a / ((1.0 + rate) ** y) for a, y in zip(amounts, years))


def xirr(cashflows: List[CashFlow]) -> Optional[float]:
    """Return the annualized internal rate of return, or None if undefined."""
    if len(cashflows) < 2:
        return None

    t0 = min(d for d, _ in cashflows)
    years = [(d - t0).days / 365.0 for d, _ in cashflows]
    amounts = [a for _, a in cashflows]

    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None

    # Newton's method first.
    rate = 0.1
    for _ in range(100):
        f = _npv(rate, years, amounts)
        deriv = sum(-y * a / ((1.0 + rate) ** (y + 1.0)) for a, y in zip(amounts, years))
        if deriv == 0:
            break
        new_rate = rate - f / deriv
        if new_rate <= -0.9999:
            new_rate = (rate - 0.9999) / 2.0
        if abs(new_rate - rate) < 1e-8:
            rate = new_rate
            break
        rate = new_rate
    if rate > -0.9999 and abs(_npv(rate, years, amounts)) < 1e-4:
        return rate

    # Fallback: bisection on a wide bracket.
    lo, hi = -0.9999, 1000.0
    f_lo = _npv(lo, years, amounts)
    f_hi = _npv(hi, years, amounts)
    if f_lo * f_hi > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2.0
        f_mid = _npv(mid, years, amounts)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0
