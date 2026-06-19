"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field

Market = Literal["a", "hk", "us", "etf"]


class BacktestRequest(BaseModel):
    market: Market
    code: str = Field(..., min_length=1, description="股票/ETF 代码或美股 ticker")
    start: str = Field(..., description="开始月份 YYYY-MM")
    end: str = Field(..., description="结束月份 YYYY-MM")
    strategy_type: Literal["amount", "shares"] = "amount"
    strategy_value: float = Field(..., gt=0, description="每月金额(amount) 或 每月股数(shares)")
    dividend_mode: Literal["reinvest", "cash"] = "reinvest"
    invest_day: int = Field(1, ge=1, le=28, description="每月定投目标日(取当日或之后首个交易日)")
    lot_override: Optional[int] = Field(None, ge=1, description="手动指定每手股数")
