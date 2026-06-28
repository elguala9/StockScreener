import logging
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import json

import yfinance as yf

from .models import StockData


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    name: str = ""
    needs_api_key: bool = False

    @abstractmethod
    def fetch_ticker(self, ticker: str) -> StockData:
        ...


class YahooFinanceProvider(DataProvider):
    name = "Yahoo Finance"
    needs_api_key = False

    def fetch_ticker(self, ticker: str) -> StockData:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
                return StockData(ticker=ticker, error="Nessun dato disponibile")

            market_cap = _safe_float(info.get("marketCap"))
            current_price = _safe_float(info.get("currentPrice")) or _safe_float(info.get("regularMarketPrice"))
            fcf_val = _safe_float(info.get("freeCashflow"))

            enterprise_value = _safe_float(info.get("enterpriseValue"))
            ebitda = _safe_float(info.get("ebitda"))
            ev_ebitda = None
            if enterprise_value is not None and ebitda is not None and ebitda != 0:
                ev_ebitda = enterprise_value / ebitda

            fcf_yield = None
            if fcf_val is not None and market_cap is not None and market_cap > 0:
                fcf_yield = (fcf_val / market_cap) * 100

            operating_margin = _safe_float(info.get("operatingMargins"))
            if operating_margin is not None:
                operating_margin *= 100

            net_margin = _safe_float(info.get("profitMargins"))
            if net_margin is not None:
                net_margin *= 100

            roe = _safe_float(info.get("returnOnEquity"))
            if roe is not None:
                roe *= 100

            roic = _safe_float(info.get("returnOnInvestedCapital"))
            if roic is not None:
                roic *= 100

            total_debt = _safe_float(info.get("totalDebt"))
            total_equity = _safe_float(info.get("totalStockholderEquity"))
            debt_equity = None
            if total_debt is not None and total_equity is not None and total_equity != 0:
                debt_equity = total_debt / total_equity

            revenue_growth = _safe_float(info.get("revenueGrowth"))
            if revenue_growth is not None:
                revenue_growth *= 100

            earnings_growth = _safe_float(info.get("earningsGrowth"))
            if earnings_growth is not None:
                earnings_growth *= 100

            dividend_yield = _safe_float(info.get("dividendYield"))
            if dividend_yield is not None:
                dividend_yield *= 100

            return StockData(
                ticker=ticker,
                name=info.get("longName") or info.get("shortName") or "",
                sector=info.get("sector") or "",
                industry=info.get("industry") or "",
                market_cap=market_cap,
                current_price=current_price,
                pe_ratio=_safe_float(info.get("trailingPE")),
                pb_ratio=_safe_float(info.get("priceToBook")),
                ps_ratio=_safe_float(info.get("priceToSalesTrailing12Months")),
                ev_ebitda=ev_ebitda,
                fcf=fcf_val,
                fcf_yield=fcf_yield,
                operating_margin=operating_margin,
                net_margin=net_margin,
                roe=roe,
                roic=roic,
                debt_equity=debt_equity,
                revenue_growth=revenue_growth,
                dividend_yield=dividend_yield,
                earnings_growth=earnings_growth,
            )

        except Exception as e:
            logger.debug(f"Yahoo: errore {ticker}: {e}")
            return StockData(ticker=ticker, error=str(e))


class FinnhubProvider(DataProvider):
    name = "Finnhub"
    needs_api_key = True

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base = "https://finnhub.io/api/v1"

    def _get(self, path: str, params: dict) -> Optional[dict]:
        params["token"] = self.api_key
        url = f"{self.base}{path}?{urlencode(params)}"
        try:
            req = Request(url, headers={"User-Agent": "StockScreener/1.0"})
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.debug(f"Finnhub: errore richiesta {url}: {e}")
            return None

    def fetch_ticker(self, ticker: str) -> StockData:
        try:
            profile = self._get("/stock/profile2", {"symbol": ticker})
            if not isinstance(profile, dict) or profile.get("ticker") is None:
                return StockData(ticker=ticker, error="Nessun profilo")

            metric_data = self._get("/stock/metric", {"symbol": ticker, "metric": "all"})
            metrics = metric_data.get("metric", {}) if isinstance(metric_data, dict) else {}

            quote = self._get("/quote", {"symbol": ticker})

            name = profile.get("name") or ""
            sector = profile.get("finnhubIndustry") or ""
            quote = quote if isinstance(quote, dict) else {}
            market_cap = _safe_float(profile.get("marketCapitalization"))
            if market_cap is not None:
                market_cap *= 1e6

            current_price = _safe_float(quote.get("c")) if quote else None
            if current_price == 0:
                current_price = None

            pe = _safe_float(metrics.get("peBasicExclExtraTTM"))
            pb = _safe_float(metrics.get("pbAnnual")) or _safe_float(metrics.get("pbQuarterly"))
            ps = _safe_float(metrics.get("psTTM"))
            ev_ebitda = _safe_float(metrics.get("evEbitdaTTM"))
            fcf_per_share = _safe_float(metrics.get("freeCashFlowPerShareTTM"))
            fcf_val = None
            if fcf_per_share is not None and market_cap is not None and current_price is not None and current_price > 0:
                shares = market_cap / current_price
                fcf_val = fcf_per_share * shares

            fcf_yield = None
            if fcf_val is not None and market_cap is not None and market_cap > 0:
                fcf_yield = (fcf_val / market_cap) * 100

            op_margin = _safe_float(metrics.get("operatingMarginTTM"))
            if op_margin is not None:
                op_margin *= 100

            net_margin = _safe_float(metrics.get("netProfitMarginTTM"))
            if net_margin is not None:
                net_margin *= 100

            roe = _safe_float(metrics.get("roeTTM"))
            if roe is not None:
                roe *= 100

            roic = _safe_float(metrics.get("roicTTM"))
            if roic is not None:
                roic *= 100

            de = _safe_float(metrics.get("totalDebtTotalEquityTTM"))

            rev_growth = _safe_float(metrics.get("revenueGrowthTTM"))
            if rev_growth is not None:
                rev_growth *= 100

            div_yield = _safe_float(metrics.get("dividendYieldIndicatedAnnual"))
            if div_yield is not None:
                div_yield *= 100

            return StockData(
                ticker=ticker,
                name=name,
                sector=sector or profile.get("country") or "",
                industry="",
                market_cap=market_cap,
                current_price=current_price,
                pe_ratio=pe,
                pb_ratio=pb,
                ps_ratio=ps,
                ev_ebitda=ev_ebitda,
                fcf=fcf_val,
                fcf_yield=fcf_yield,
                operating_margin=op_margin,
                net_margin=net_margin,
                roe=roe,
                roic=roic,
                debt_equity=de,
                revenue_growth=rev_growth,
                dividend_yield=div_yield,
            )

        except Exception as e:
            logger.debug(f"Finnhub: errore {ticker}: {e}")
            return StockData(ticker=ticker, error=str(e))


class AlphaVantageProvider(DataProvider):
    name = "Alpha Vantage"
    needs_api_key = True

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base = "https://www.alphavantage.co/query"

    def _get(self, params: dict) -> Optional[dict]:
        params["apikey"] = self.api_key
        url = f"{self.base}?{urlencode(params)}"
        try:
            req = Request(url, headers={"User-Agent": "StockScreener/1.0"})
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.debug(f"AlphaV: errore richiesta: {e}")
            return None

    def fetch_ticker(self, ticker: str) -> StockData:
        try:
            overview = self._get({"function": "OVERVIEW", "symbol": ticker})
            if not isinstance(overview, dict) or overview.get("Symbol") is None:
                return StockData(ticker=ticker, error="Nessun dato")

            quote = self._get({"function": "GLOBAL_QUOTE", "symbol": ticker})
            price = None
            if quote and isinstance(quote, dict) and "Global Quote" in quote:
                price = _safe_float(quote["Global Quote"].get("05. price"))

            market_cap = _safe_float(overview.get("MarketCapitalization"))
            pe = _safe_float(overview.get("PERatio"))
            pb = _safe_float(overview.get("PriceToBookRatio"))
            ps = _safe_float(overview.get("PriceToSalesRatioTTM"))
            ev_ebitda = _safe_float(overview.get("EVToEBITDA"))
            fcf_val = _safe_float(overview.get("FreeCashFlow"))
            op_margin = _safe_float(overview.get("OperatingMarginTTM"))
            if op_margin is not None:
                op_margin *= 100
            net_margin = _safe_float(overview.get("ProfitMargin"))
            if net_margin is not None:
                net_margin *= 100
            roe = _safe_float(overview.get("ReturnOnEquityTTM"))
            if roe is not None:
                roe *= 100
            roic = _safe_float(overview.get("ReturnOnInvestedCapitalTTM"))
            if roic is not None:
                roic *= 100
            debt_equity = _safe_float(overview.get("DebtToEquityRatio"))
            rev_growth = _safe_float(overview.get("RevenueGrowth"))
            if rev_growth is not None:
                rev_growth *= 100
            div_yield = _safe_float(overview.get("DividendYield"))
            if div_yield is not None:
                div_yield *= 100

            fcf_yield = None
            if fcf_val is not None and market_cap is not None and market_cap > 0:
                fcf_yield = (fcf_val / market_cap) * 100

            return StockData(
                ticker=ticker,
                name=overview.get("Name") or "",
                sector=overview.get("Sector") or "",
                industry=overview.get("Industry") or "",
                market_cap=market_cap,
                current_price=price,
                pe_ratio=pe,
                pb_ratio=pb,
                ps_ratio=ps,
                ev_ebitda=ev_ebitda,
                fcf=fcf_val,
                fcf_yield=fcf_yield,
                operating_margin=op_margin,
                net_margin=net_margin,
                roe=roe,
                roic=roic,
                debt_equity=debt_equity,
                revenue_growth=rev_growth,
                dividend_yield=div_yield,
            )

        except Exception as e:
            logger.debug(f"AlphaV: errore {ticker}: {e}")
            return StockData(ticker=ticker, error=str(e))


_PROVIDERS: dict[str, type[DataProvider]] = {}


def register_provider(cls: type[DataProvider]):
    key = cls.name.lower().replace(" ", "")
    _PROVIDERS[key] = cls


def get_provider(name: str, api_key: str = "") -> Optional[DataProvider]:
    key = name.lower().replace(" ", "").replace("-", "")
    cls = _PROVIDERS.get(key)
    if cls is None:
        return None
    if cls.needs_api_key and not api_key:
        logger.warning(f"{cls.name} richiede una API key")
        return None
    if cls.needs_api_key:
        return cls(api_key=api_key)
    return cls()


def get_provider_names() -> list[str]:
    return [cls.name for cls in _PROVIDERS.values()]


register_provider(YahooFinanceProvider)
register_provider(FinnhubProvider)
register_provider(AlphaVantageProvider)
