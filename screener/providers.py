import logging
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import json

import yfinance as yf

from .models import StockData

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

            market_cap = info.get("marketCap")
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            fcf_val = info.get("freeCashflow")

            enterprise_value = info.get("enterpriseValue")
            ebitda = info.get("ebitda")
            ev_ebitda = None
            if enterprise_value is not None and ebitda is not None and ebitda != 0:
                ev_ebitda = enterprise_value / ebitda

            fcf_yield = None
            if fcf_val is not None and market_cap is not None and market_cap > 0:
                fcf_yield = (fcf_val / market_cap) * 100

            operating_margin = info.get("operatingMargins")
            if operating_margin is not None:
                operating_margin *= 100

            net_margin = info.get("profitMargins")
            if net_margin is not None:
                net_margin *= 100

            roe = info.get("returnOnEquity")
            if roe is not None:
                roe *= 100

            roic = info.get("returnOnInvestedCapital")
            if roic is not None:
                roic *= 100

            total_debt = info.get("totalDebt")
            total_equity = info.get("totalStockholderEquity")
            debt_equity = None
            if total_debt is not None and total_equity is not None and total_equity != 0:
                debt_equity = total_debt / total_equity

            revenue_growth = info.get("revenueGrowth")
            if revenue_growth is not None:
                revenue_growth *= 100

            earnings_growth = info.get("earningsGrowth")
            if earnings_growth is not None:
                earnings_growth *= 100

            dividend_yield = info.get("dividendYield")
            if dividend_yield is not None:
                dividend_yield *= 100

            return StockData(
                ticker=ticker,
                name=info.get("longName") or info.get("shortName") or "",
                sector=info.get("sector") or "",
                industry=info.get("industry") or "",
                market_cap=market_cap,
                current_price=current_price,
                pe_ratio=info.get("trailingPE"),
                pb_ratio=info.get("priceToBook"),
                ps_ratio=info.get("priceToSalesTrailing12Months"),
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
            if profile is None or profile.get("ticker") is None:
                return StockData(ticker=ticker, error="Nessun profilo")

            metric_data = self._get("/stock/metric", {"symbol": ticker, "metric": "all"})
            metrics = metric_data.get("metric", {}) if metric_data else {}

            quote = self._get("/quote", {"symbol": ticker})

            name = profile.get("name") or ""
            sector = profile.get("finnhubIndustry") or ""
            market_cap = profile.get("marketCapitalization")
            if market_cap is not None:
                market_cap *= 1e6

            current_price = quote.get("c") if quote else None
            if current_price == 0:
                current_price = None

            pe = metrics.get("peBasicExclExtraTTM")
            pb = metrics.get("pbAnnual") or metrics.get("pbQuarterly")
            ps = metrics.get("psTTM")
            ev_ebitda = metrics.get("evEbitdaTTM")
            fcf_per_share = metrics.get("freeCashFlowPerShareTTM")
            fcf_val = None
            if fcf_per_share is not None and market_cap is not None and current_price is not None and current_price > 0:
                shares = market_cap / current_price
                fcf_val = fcf_per_share * shares

            fcf_yield = None
            if fcf_val is not None and market_cap is not None and market_cap > 0:
                fcf_yield = (fcf_val / market_cap) * 100

            op_margin = metrics.get("operatingMarginTTM")
            if op_margin is not None:
                op_margin *= 100

            net_margin = metrics.get("netProfitMarginTTM")
            if net_margin is not None:
                net_margin *= 100

            roe = metrics.get("roeTTM")
            if roe is not None:
                roe *= 100

            roic = metrics.get("roicTTM")
            if roic is not None:
                roic *= 100

            de = metrics.get("totalDebtTotalEquityTTM")

            rev_growth = metrics.get("revenueGrowthTTM")
            if rev_growth is not None:
                rev_growth *= 100

            div_yield = metrics.get("dividendYieldIndicatedAnnual")
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
            if not overview or overview.get("Symbol") is None:
                return StockData(ticker=ticker, error="Nessun dato")

            quote = self._get({"function": "GLOBAL_QUOTE", "symbol": ticker})
            price = None
            if quote and "Global Quote" in quote:
                price_str = quote["Global Quote"].get("05. price", "")
                try:
                    price = float(price_str) if price_str else None
                except (ValueError, TypeError):
                    price = None

            def _f(key):
                v = overview.get(key)
                try:
                    return float(v) if v and v != "None" else None
                except (ValueError, TypeError):
                    return None

            market_cap = _f("MarketCapitalization")
            pe = _f("PERatio")
            pb = _f("PriceToBookRatio")
            ps = _f("PriceToSalesRatioTTM")
            ev_ebitda = _f("EVToEBITDA")
            fcf_val = _f("FreeCashFlow")
            op_margin = _f("OperatingMarginTTM")
            if op_margin is not None:
                op_margin *= 100
            net_margin = _f("ProfitMargin")
            if net_margin is not None:
                net_margin *= 100
            roe = _f("ReturnOnEquityTTM")
            if roe is not None:
                roe *= 100
            roic = _f("ReturnOnInvestedCapitalTTM")
            if roic is not None:
                roic *= 100
            debt_equity = _f("DebtToEquityRatio")
            rev_growth = _f("RevenueGrowth")
            if rev_growth is not None:
                rev_growth *= 100
            div_yield = _f("DividendYield")
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
