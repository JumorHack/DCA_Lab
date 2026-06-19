"""Instrument search endpoint (name or code -> resolved instrument)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..markets import list_markets
from ..services import data

router = APIRouter()


@router.get("/markets")
def markets():
    return {"markets": list_markets()}


@router.get("/search")
def search(
    market: str = Query(..., description="a | hk | us | etf"),
    q: str = Query(..., min_length=1, description="名称或代码关键字"),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        results = data.search(market, q, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # network / akshare failures
        raise HTTPException(status_code=502, detail=f"数据源查询失败: {e}")
    return {"results": results}


@router.delete("/cache")
def clear_cache(
    market: str = Query(..., description="a | hk | us | etf"),
    code: str = Query(..., min_length=1, description="代码或名称"),
):
    """删除指定标的的本地缓存(行情/分红), 下次查询会重新拉取最新数据。"""
    try:
        resolved = data.resolve_instrument(market, code).get("code", code).strip()
    except Exception:
        resolved = code.strip()
    deleted = db.clear_instrument_cache(market, resolved)
    return {"ok": True, "market": market, "code": resolved, "deleted": deleted}
