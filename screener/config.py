from dataclasses import dataclass, fields
from typing import Optional


SHORT_TO_LONG = {
    "pe": "pe",
    "pb": "pb",
    "ps": "ps",
    "ev_ebitda": "ev_ebitda",
    "fcf_yield": "fcf_yield",
    "op_margin": "operating_margin",
    "net_margin": "net_margin",
    "roe": "roe",
    "roic": "roic",
    "debt_equity": "debt_equity",
    "market_cap": "market_cap",
    "div_yield": "dividend_yield",
    "rev_growth": "revenue_growth",
}

LONG_TO_SHORT = {v: k for k, v in SHORT_TO_LONG.items()}


@dataclass
class ScreenerConfig:
    pe_min: Optional[float] = None
    pe_max: Optional[float] = None
    pb_min: Optional[float] = None
    pb_max: Optional[float] = None
    ps_min: Optional[float] = None
    ps_max: Optional[float] = None
    ev_ebitda_min: Optional[float] = None
    ev_ebitda_max: Optional[float] = None
    fcf_yield_min: Optional[float] = None
    fcf_yield_max: Optional[float] = None
    operating_margin_min: Optional[float] = None
    operating_margin_max: Optional[float] = None
    net_margin_min: Optional[float] = None
    net_margin_max: Optional[float] = None
    roe_min: Optional[float] = None
    roe_max: Optional[float] = None
    roic_min: Optional[float] = None
    roic_max: Optional[float] = None
    debt_equity_min: Optional[float] = None
    debt_equity_max: Optional[float] = None
    market_cap_min: Optional[float] = None
    market_cap_max: Optional[float] = None
    dividend_yield_min: Optional[float] = None
    dividend_yield_max: Optional[float] = None
    revenue_growth_min: Optional[float] = None
    revenue_growth_max: Optional[float] = None

    def is_empty(self) -> bool:
        return all(v is None for v in self.__dict__.values())

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    @classmethod
    def from_filter_dict(cls, data: dict[str, tuple[Optional[float], Optional[float]]]) -> "ScreenerConfig":
        kwargs = {}
        for short, (lo, hi) in data.items():
            long_name = SHORT_TO_LONG.get(short, short)
            if lo is not None:
                kwargs[f"{long_name}_min"] = float(lo)
            if hi is not None:
                kwargs[f"{long_name}_max"] = float(hi)
        return cls(**kwargs)
