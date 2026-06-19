"""Local SQLite persistence layer (cache for akshare data).

Tables
------
instruments    : 各市场标的清单 (供搜索 / 名称<->代码)
price_history  : 日线行情, 不复权(close_raw) + 后复权(close_hfq)
dividends      : 分红 / 送转 记录
fetch_log      : 记录每个 (market, code, dataset) 已覆盖的日期区间与抓取时间

All access goes through SQLAlchemy on a single local sqlite file. Pandas is used
for bulk reads; writes use `INSERT OR REPLACE` so repeated fetches are idempotent.
"""
from __future__ import annotations

import os
import datetime as dt
from typing import Optional, List, Dict, Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "dca_cache.sqlite")

_engine: Optional[Engine] = None

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS instruments (
        market     TEXT NOT NULL,
        code       TEXT NOT NULL,
        name       TEXT,
        lot        INTEGER,
        currency   TEXT,
        ak_symbol  TEXT,
        updated_at TEXT,
        PRIMARY KEY (market, code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_history (
        market    TEXT NOT NULL,
        code      TEXT NOT NULL,
        date      TEXT NOT NULL,
        close_raw REAL,
        close_hfq REAL,
        open      REAL,
        high      REAL,
        low       REAL,
        volume    REAL,
        PRIMARY KEY (market, code, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dividends (
        market         TEXT NOT NULL,
        code           TEXT NOT NULL,
        ex_date        TEXT NOT NULL,
        cash_per_share REAL,
        bonus_ratio    REAL,
        split_factor   REAL,
        raw            TEXT,
        PRIMARY KEY (market, code, ex_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fetch_log (
        market      TEXT NOT NULL,
        code        TEXT NOT NULL,
        dataset     TEXT NOT NULL,
        range_start TEXT,
        range_end   TEXT,
        fetched_at  TEXT,
        PRIMARY KEY (market, code, dataset)
    )
    """,
]


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
        init_db(_engine)
    return _engine


def init_db(engine: Optional[Engine] = None) -> None:
    engine = engine or get_engine()
    with engine.begin() as conn:
        for ddl in _SCHEMA:
            conn.execute(text(ddl))


# --------------------------------------------------------------------------- #
# generic helpers
# --------------------------------------------------------------------------- #
def _upsert(table: str, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    cols = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = text(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})")
    with get_engine().begin() as conn:
        conn.execute(sql, rows)


# --------------------------------------------------------------------------- #
# fetch_log
# --------------------------------------------------------------------------- #
def get_fetch_log(market: str, code: str, dataset: str) -> Optional[Dict[str, Any]]:
    sql = text(
        "SELECT market, code, dataset, range_start, range_end, fetched_at "
        "FROM fetch_log WHERE market=:m AND code=:c AND dataset=:d"
    )
    with get_engine().connect() as conn:
        row = conn.execute(sql, {"m": market, "c": code, "d": dataset}).mappings().first()
    return dict(row) if row else None


def set_fetch_log(
    market: str,
    code: str,
    dataset: str,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
) -> None:
    _upsert(
        "fetch_log",
        ["market", "code", "dataset", "range_start", "range_end", "fetched_at"],
        [
            {
                "market": market,
                "code": code,
                "dataset": dataset,
                "range_start": range_start,
                "range_end": range_end,
                "fetched_at": now_iso(),
            }
        ],
    )


# --------------------------------------------------------------------------- #
# instruments
# --------------------------------------------------------------------------- #
def upsert_instruments(rows: List[Dict[str, Any]]) -> None:
    for r in rows:
        r.setdefault("updated_at", now_iso())
    _upsert(
        "instruments",
        ["market", "code", "name", "lot", "currency", "ak_symbol", "updated_at"],
        rows,
    )


def count_instruments(market: str) -> int:
    sql = text("SELECT COUNT(*) FROM instruments WHERE market=:m")
    with get_engine().connect() as conn:
        return int(conn.execute(sql, {"m": market}).scalar() or 0)


def get_instrument(market: str, code: str) -> Optional[Dict[str, Any]]:
    sql = text(
        "SELECT market, code, name, lot, currency, ak_symbol FROM instruments "
        "WHERE market=:m AND code=:c"
    )
    with get_engine().connect() as conn:
        row = conn.execute(sql, {"m": market, "c": code}).mappings().first()
    return dict(row) if row else None


def find_instrument_by_ak_symbol(market: str, ak_symbol: str) -> Optional[Dict[str, Any]]:
    sql = text(
        "SELECT market, code, name, lot, currency, ak_symbol FROM instruments "
        "WHERE market=:m AND ak_symbol=:s"
    )
    with get_engine().connect() as conn:
        row = conn.execute(sql, {"m": market, "s": ak_symbol}).mappings().first()
    return dict(row) if row else None


def search_instruments(market: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    like = f"%{query}%"
    sql = text(
        "SELECT market, code, name, lot, currency, ak_symbol FROM instruments "
        "WHERE market=:m AND (code LIKE :q OR name LIKE :q OR ak_symbol LIKE :q) "
        "ORDER BY CASE WHEN code=:exact THEN 0 WHEN code LIKE :prefix THEN 1 ELSE 2 END, "
        "length(code), code LIMIT :lim"
    )
    with get_engine().connect() as conn:
        rows = conn.execute(
            sql,
            {
                "m": market,
                "q": like,
                "exact": query,
                "prefix": f"{query}%",
                "lim": limit,
            },
        ).mappings().all()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# price_history
# --------------------------------------------------------------------------- #
def upsert_price_history(market: str, code: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    rows: List[Dict[str, Any]] = []
    for rec in df.to_dict(orient="records"):
        rows.append(
            {
                "market": market,
                "code": code,
                "date": rec["date"],
                "close_raw": _num(rec.get("close_raw")),
                "close_hfq": _num(rec.get("close_hfq")),
                "open": _num(rec.get("open")),
                "high": _num(rec.get("high")),
                "low": _num(rec.get("low")),
                "volume": _num(rec.get("volume")),
            }
        )
    _upsert(
        "price_history",
        ["market", "code", "date", "close_raw", "close_hfq", "open", "high", "low", "volume"],
        rows,
    )


def read_price_history(market: str, code: str, start: str, end: str) -> pd.DataFrame:
    sql = (
        "SELECT date, close_raw, close_hfq, open, high, low, volume FROM price_history "
        "WHERE market=:m AND code=:c AND date>=:s AND date<=:e ORDER BY date"
    )
    with get_engine().connect() as conn:
        df = pd.read_sql_query(text(sql), conn, params={"m": market, "c": code, "s": start, "e": end})
    return df


# --------------------------------------------------------------------------- #
# dividends
# --------------------------------------------------------------------------- #
def replace_dividends(market: str, code: str, rows: List[Dict[str, Any]]) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM dividends WHERE market=:m AND code=:c"),
            {"m": market, "c": code},
        )
    if rows:
        _upsert(
            "dividends",
            ["market", "code", "ex_date", "cash_per_share", "bonus_ratio", "split_factor", "raw"],
            rows,
        )


def read_dividends(market: str, code: str, start: str, end: str) -> List[Dict[str, Any]]:
    sql = text(
        "SELECT ex_date, cash_per_share, bonus_ratio, split_factor FROM dividends "
        "WHERE market=:m AND code=:c AND ex_date>=:s AND ex_date<=:e ORDER BY ex_date"
    )
    with get_engine().connect() as conn:
        rows = conn.execute(
            sql, {"m": market, "c": code, "s": start, "e": end}
        ).mappings().all()
    return [dict(r) for r in rows]


def clear_instrument_cache(market: str, code: str) -> Dict[str, int]:
    """删除某个标的的本地缓存(行情/分红/对应抓取记录), 保留全市场标的清单。"""
    deleted: Dict[str, int] = {}
    with get_engine().begin() as conn:
        for table in ("price_history", "dividends", "fetch_log"):
            res = conn.execute(
                text(f"DELETE FROM {table} WHERE market=:m AND code=:c"),
                {"m": market, "c": code},
            )
            deleted[table] = int(res.rowcount or 0)
    return deleted


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None
