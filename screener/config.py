from dataclasses import dataclass
from typing import Optional


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
