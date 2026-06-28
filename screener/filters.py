import logging
from .models import StockData
from .config import ScreenerConfig

logger = logging.getLogger(__name__)


def apply_filters(stock: StockData, config: ScreenerConfig) -> bool:
    if config.is_empty():
        stock.passed = True
        stock.reasons = ["Nessun filtro impostato"]
        return True

    passed = True
    reasons: list[str] = []

    def check(
        label: str,
        value: float | None,
        lo: float | None,
        hi: float | None,
    ):
        nonlocal passed
        if not isinstance(value, (int, float)):
            return
        if lo is not None and not isinstance(lo, (int, float)):
            lo = None
        if hi is not None and not isinstance(hi, (int, float)):
            hi = None
        if lo is not None and hi is not None:
            ok = lo <= value <= hi
            symbol = "✓" if ok else "✗"
            reasons.append(
                f"{symbol} {label}: {value:.2f} (range: {lo:.2f} - {hi:.2f})"
            )
            if not ok:
                passed = False
        elif lo is not None:
            ok = value >= lo
            symbol = "✓" if ok else "✗"
            reasons.append(f"{symbol} {label}: {value:.2f} (min: {lo:.2f})")
            if not ok:
                passed = False
        elif hi is not None:
            ok = value <= hi
            symbol = "✓" if ok else "✗"
            reasons.append(f"{symbol} {label}: {value:.2f} (max: {hi:.2f})")
            if not ok:
                passed = False

    check("P/E", stock.pe_ratio, config.pe_min, config.pe_max)
    check("P/B", stock.pb_ratio, config.pb_min, config.pb_max)
    check("P/S", stock.ps_ratio, config.ps_min, config.ps_max)
    check("EV/EBITDA", stock.ev_ebitda, config.ev_ebitda_min, config.ev_ebitda_max)
    check("FCF Yield %", stock.fcf_yield, config.fcf_yield_min, config.fcf_yield_max)
    check("Margine Op. %", stock.operating_margin, config.operating_margin_min, config.operating_margin_max)
    check("Margine Netto %", stock.net_margin, config.net_margin_min, config.net_margin_max)
    check("ROE %", stock.roe, config.roe_min, config.roe_max)
    check("ROIC %", stock.roic, config.roic_min, config.roic_max)
    check("Debt/Equity", stock.debt_equity, config.debt_equity_min, config.debt_equity_max)
    check("Dividend Yield %", stock.dividend_yield, config.dividend_yield_min, config.dividend_yield_max)
    check("Crescita Ricavi %", stock.revenue_growth, config.revenue_growth_min, config.revenue_growth_max)

    if config.market_cap_min is not None or config.market_cap_max is not None:
        mc_bn = (stock.market_cap / 1e9) if stock.market_cap is not None else None
        check("Market Cap (B$)", mc_bn, config.market_cap_min, config.market_cap_max)

    stock.passed = passed
    stock.reasons = reasons

    if passed:
        logger.debug(f"{stock.ticker}: PASS ({len(reasons)} check)")
    else:
        logger.debug(f"{stock.ticker}: FAIL")

    return passed


def filter_stocks(
    stocks: list[StockData], config: ScreenerConfig
) -> tuple[list[StockData], list[StockData]]:
    passed_list: list[StockData] = []
    failed_list: list[StockData] = []

    for stock in stocks:
        if stock.error:
            failed_list.append(stock)
            continue
        apply_filters(stock, config)
        if stock.passed:
            passed_list.append(stock)
        else:
            failed_list.append(stock)

    return passed_list, failed_list
