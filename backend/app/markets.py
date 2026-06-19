"""Per-market configuration: lot size, currency, display name.

Lot size (每手股数):
  - A股 / 场内 ETF: 100 股一手
  - 港股: 每手股数不一(无统一 API), 默认 100, 前端可手动覆盖
  - 美股: 1 股即可买入
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class MarketConfig:
    key: str
    name: str
    currency: str
    default_lot: int
    # 港股每手股数无官方接口, 标记为需要用户确认 / 可覆盖
    lot_is_uncertain: bool = False
    # 该市场的分红明细在 akshare 是否较可靠
    dividend_reliable: bool = False


MARKETS: Dict[str, MarketConfig] = {
    "a": MarketConfig("a", "A股", "CNY", 100, dividend_reliable=True),
    "hk": MarketConfig("hk", "港股", "HKD", 100, lot_is_uncertain=True),
    "us": MarketConfig("us", "美股", "USD", 1),
    "etf": MarketConfig("etf", "场内ETF", "CNY", 100),
}


def get_market(key: str) -> MarketConfig:
    cfg = MARKETS.get(key)
    if cfg is None:
        raise ValueError(f"未知市场: {key}")
    return cfg


def list_markets():
    return [
        {
            "key": m.key,
            "name": m.name,
            "currency": m.currency,
            "default_lot": m.default_lot,
            "lot_is_uncertain": m.lot_is_uncertain,
            "dividend_reliable": m.dividend_reliable,
        }
        for m in MARKETS.values()
    ]
