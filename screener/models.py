from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StockData:
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: Optional[float] = None
    current_price: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    fcf: Optional[float] = None
    fcf_yield: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    debt_equity: Optional[float] = None
    revenue_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    earnings_growth: Optional[float] = None
    passed: bool = False
    reasons: list[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Nome": self.name,
            "Settore": self.sector,
            "Industria": self.industry,
            "Market Cap": _fmt_bn(self.market_cap),
            "Prezzo": _fmt(self.current_price),
            "P/E": _fmt(self.pe_ratio),
            "P/B": _fmt(self.pb_ratio),
            "P/S": _fmt(self.ps_ratio),
            "EV/EBITDA": _fmt(self.ev_ebitda),
            "FCF": _fmt_bn(self.fcf),
            "FCF Yield %": _fmt(self.fcf_yield),
            "Margine Op. %": _fmt(self.operating_margin),
            "Margine Netto %": _fmt(self.net_margin),
            "ROE %": _fmt(self.roe),
            "ROIC %": _fmt(self.roic),
            "Debt/Equity": _fmt(self.debt_equity),
            "Crescita Ricavi %": _fmt(self.revenue_growth),
            "Dividend Yield %": _fmt(self.dividend_yield),
            "Supera Filtri": self.passed,
            "Motivazioni": "; ".join(self.reasons) if self.reasons else "",
            "Errore": self.error or "",
        }


def _fmt(val: Optional[float], decimals: int = 2) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    return f"{val:.{decimals}f}"


def _fmt_bn(val: Optional[float]) -> str:
    if val is None:
        return ""
    val_bn = val / 1e9
    return f"{val_bn:.2f}B"
