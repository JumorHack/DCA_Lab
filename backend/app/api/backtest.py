"""DCA backtest endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import BacktestRequest
from ..services import engine

router = APIRouter()


@router.post("/backtest")
def backtest(req: BacktestRequest):
    try:
        return engine.run_backtest(
            market=req.market,
            code=req.code,
            start=req.start,
            end=req.end,
            strategy_type=req.strategy_type,
            strategy_value=req.strategy_value,
            dividend_mode=req.dividend_mode,
            invest_day=req.invest_day,
            lot_override=req.lot_override,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # network / akshare / unexpected
        raise HTTPException(status_code=502, detail=f"回测失败: {e}")
