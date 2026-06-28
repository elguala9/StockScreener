import logging
import csv
import io
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen
import pandas as pd

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"

logger = logging.getLogger(__name__)

DAX_40_TICKERS = [
    "ADS.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE",
    "BMW.DE", "CBK.DE", "CON.DE", "DAI.DE", "DB1.DE",
    "DBK.DE", "DPW.DE", "DTE.DE", "DWNI.DE", "EOAN.DE",
    "FME.DE", "FRE.DE", "HEI.DE", "HEN3.DE", "IFX.DE",
    "LIN.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "PUM.DE",
    "QIA.DE", "RWE.DE", "SAP.DE", "SIE.DE", "SY1.DE",
    "VNA.DE", "ZAL.DE",
]

FTSE_100_TICKERS = [
    "AAL.L", "ABF.L", "ADM.L", "AHT.L", "ANTO.L",
    "ARM.L", "AUTO.L", "AV.L", "AZN.L", "BA.L",
    "BARC.L", "BATS.L", "BDEV.L", "BKG.L", "BLND.L",
    "BNZL.L", "BP.L", "BT-A.L", "CCH.L", "CPG.L",
    "CRDA.L", "CRH.L", "DCC.L", "DGE.L", "EVOK.L",
    "EXPN.L", "FCIT.L", "FLTR.L", "FRES.L", "GSK.L",
    "HLMA.L", "HLN.L", "HSBA.L", "IAG.L", "III.L",
    "IMB.L", "INF.L", "ITRK.L", "JD.L", "JMAT.L",
    "KGF.L", "LAND.L", "LGEN.L", "LLOY.L", "MNG.L",
    "MRO.L", "NG.L", "NXT.L", "OCDO.L", "PHNX.L",
    "PRU.L", "PSH.L", "PSON.L", "RKT.L", "REL.L",
    "RIO.L", "RR.L", "RTO.L", "SBRY.L", "SDR.L",
    "SGE.L", "SGRO.L", "SHEL.L", "SKG.L", "SMIN.L",
    "SMWH.L", "SN.L", "SPX.L", "SSE.L", "STAN.L",
    "STJ.L", "SVT.L", "TSCO.L", "TW.L", "ULVR.L",
    "UU.L", "VOD.L", "WEIR.L", "WPP.L",
]

NIKKEI_225_TICKERS = [
    "4502.T", "4503.T", "4519.T", "4523.T", "4568.T",
    "4578.T", "4689.T", "4704.T", "4751.T", "4755.T",
    "4901.T", "4911.T", "5108.T", "5201.T", "5214.T",
    "5301.T", "5401.T", "5406.T", "5411.T", "5631.T",
    "5706.T", "5711.T", "5713.T", "5714.T", "5801.T",
    "5802.T", "5803.T", "5901.T", "6113.T", "6302.T",
    "6305.T", "6326.T", "6361.T", "6367.T", "6471.T",
    "6472.T", "6473.T", "6479.T", "6501.T", "6502.T",
    "6503.T", "6504.T", "6506.T", "6526.T", "6586.T",
    "6594.T", "6645.T", "6674.T", "6701.T", "6702.T",
    "6703.T", "6723.T", "6724.T", "6727.T", "6728.T",
    "6752.T", "6753.T", "6758.T", "6762.T", "6770.T",
    "6841.T", "6857.T", "6861.T", "6902.T", "6951.T",
    "6952.T", "6954.T", "6967.T", "6971.T", "6976.T",
    "6981.T", "6988.T", "7003.T", "7004.T", "7011.T",
    "7012.T", "7013.T", "7201.T", "7202.T", "7203.T",
    "7211.T", "7261.T", "7267.T", "7269.T", "7270.T",
    "7272.T", "7276.T", "7731.T", "7733.T", "7741.T",
    "7751.T", "7752.T", "7762.T", "7832.T", "7911.T",
    "7912.T", "7951.T", "8001.T", "8002.T", "8015.T",
    "8031.T", "8035.T", "8046.T", "8053.T", "8058.T",
    "8113.T", "8233.T", "8252.T", "8253.T", "8267.T",
    "8270.T", "8303.T", "8306.T", "8308.T", "8309.T",
    "8316.T", "8331.T", "8332.T", "8354.T", "8355.T",
    "8411.T", "8591.T", "8593.T", "8601.T", "8604.T",
    "8630.T", "8697.T", "8715.T", "8725.T", "8750.T",
    "8766.T", "8795.T", "8802.T", "8804.T", "8830.T",
    "8876.T", "8897.T", "8919.T", "9001.T", "9005.T",
    "9007.T", "9008.T", "9009.T", "9020.T", "9021.T",
    "9022.T", "9031.T", "9041.T", "9042.T", "9043.T",
    "9048.T", "9090.T", "9101.T", "9104.T", "9107.T",
    "9201.T", "9202.T", "9301.T", "9412.T", "9432.T",
    "9433.T", "9434.T", "9437.T", "9501.T", "9502.T",
    "9503.T", "9509.T", "9513.T", "9531.T", "9532.T",
    "9602.T", "9613.T", "9681.T", "9729.T", "9735.T",
    "9766.T", "9843.T", "9861.T", "9983.T", "9984.T",
]

HARDCODED_INDICES: dict[str, tuple[str, list[str]]] = {
    "dax40": ("DAX 40 (40) — Germania", DAX_40_TICKERS),
    "ftse100": ("FTSE 100 (100) — Regno Unito", FTSE_100_TICKERS),
    "nikkei225": ("Nikkei 225 (225) — Giappone", NIKKEI_225_TICKERS),
}

FULL_EXCHANGE_LISTINGS: dict[str, tuple[str, str, str]] = {
    "nse_india":     ("NSE India (tutte) — India",     "List_of_companies_listed_on_the_National_Stock_Exchange_of_India", "symbol", ".NS"),
    "szse":          ("SZSE (tutte) — Cina",           "List_of_companies_listed_on_the_Shenzhen_Stock_Exchange",          "code",   ".SZ"),
}

WIKI_INDICES: dict[str, tuple] = {
    "sp500":       ("S&P 500 — USA",               "List_of_S%26P_500_companies", "Symbol",       0, ""),
    "nasdaq100":   ("NASDAQ 100 — USA",            "Nasdaq-100",                    "Ticker",       5, ""),
    "cac40":       ("CAC 40 — Francia",            "CAC_40",                        "Ticker",       4, ".PA"),
    "ftsemib":     ("FTSE MIB — Italia",           "FTSE_MIB",                      "Ticker",       1, ".MI"),
    "ibex35":      ("IBEX 35 — Spagna",            "IBEX_35",                       "Ticker",       2, ".MC"),
    "aex":         ("AEX — Paesi Bassi",           "AEX_index",                     "Ticker",       3, ".AS"),
    "smi":         ("SMI — Svizzera",              "Swiss_Market_Index",            "Ticker",       2, ".SW"),
    "omx30":       ("OMX 30 — Svezia",             "OMX_Stockholm_30",              "Ticker",       1, ".ST"),
    "bel20":       ("BEL 20 — Belgio",             "BEL_20",                        "Ticker symbol",2, ".BR"),
    "obx":         ("OBX — Norvegia",              "OBX_index",                     "Ticker symbol",0, ".OL"),
    "wig30":       ("WIG30 — Polonia",             "WIG30",                         "Ticker",       1, ".WA"),
    "tsx60":       ("S&P/TSX 60 — Canada",         "S&P/TSX_60",                    "Symbol",       1, ".TO"),
    "hsi":         ("Hang Seng — Hong Kong",       "Hang_Seng_Index",               "Ticker",       6, ".HK"),
    "nifty50":     ("NIFTY 50 — India",            "NIFTY_50",                      "Symbol",       1, ".NS"),
    "sensex":      ("BSE SENSEX — India",          "BSE_SENSEX",                    "Symbol",       2, ".BO"),
    "asx200":      ("S&P/ASX 200 — Australia",     "S&P/ASX_200",                   "Code",         2, ".AX"),
    "iseq20":      ("ISEQ 20 — Irlanda",           "ISEQ_20",                       "MNEM code",    0, ".IR"),
    "psi20":       ("PSI-20 — Portogallo",         "PSI_20",                        "Ticker",       2, ".LI"),
    "omxc25":      ("OMX Copen. 25 — Danimarca",   "OMX_Copenhagen_25",             "Ticker symbol",0, ".CO"),
    "omxh25":      ("OMX Hels. 25 — Finlandia",    "OMX_Helsinki_25",               "Ticker",       1, ".HE"),
    "sse50":       ("SSE 50 — Cina",               "SSE_50_Index",                  "Ticker symbol",1, ".SS",  {"SSE": ".SS"}),
    "ipc":         ("IPC — Messico",               "Índice_de_Precios_y_Cotizaciones","Symbol",      0, ".MX"),
    "kse30":       ("KSE 30 — Pakistan",           "KSE_30_Index",                  "Ticker",       1, ".PSX", {"PSX": ".KSE"}),
    "kospi":       ("KOSPI — Corea del Sud",       "KOSPI",                         "Symbol",       5, ".KS",  {"KRX": ".KS"}),
    "ta35":        ("TA-35 — Israele",             "TA-35",                         "Ticker",       1, ".TA"),
}

NASDAQ_FTP_URL = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
OTHER_FTP_URL = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"


def _fetch_ftp_tickers(url: str, exchange_label: str, keep_col: str = "Symbol") -> Optional[list[str]]:
    try:
        resp = urlopen(url, timeout=30)
        content = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content), delimiter="|")
        tickers = []
        for row in reader:
            sym = row.get(keep_col, "").strip()
            if sym and "$" not in sym:
                tickers.append(sym)
        logger.info(f"Scaricati {len(tickers)} ticker da NASDAQ Trader per {exchange_label}")
        return tickers
    except Exception as e:
        logger.error(f"Errore scaricando ticker da {url}: {e}")
        return None


def _fetch_nasdaq_full() -> Optional[list[str]]:
    return _fetch_ftp_tickers(NASDAQ_FTP_URL, "NASDAQ completo")


def _fetch_other_listed(exchange_code: str) -> Optional[list[str]]:
    try:
        resp = urlopen(OTHER_FTP_URL, timeout=30)
        content = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content), delimiter="|")
        tickers = []
        for row in reader:
            ex = row.get("Exchange", "").strip()
            sym = row.get("ACT Symbol", "").strip()
            test_issue = row.get("Test Issue", "").strip()
            if test_issue == "Y":
                continue
            if ex == exchange_code and sym and "$" not in sym:
                tickers.append(sym)
        logger.info(f"Scaricati {len(tickers)} ticker (exchange={exchange_code}) da NASDAQ Trader")
        return tickers
    except Exception as e:
        logger.error(f"Errore scaricando {exchange_code}: {e}")
        return None


EXCHANGE_SOURCES: dict[str, tuple[str, str]] = {
    "nasdaq": ("NASDAQ (tutti) — USA", "ftp"),
    "nyse": ("NYSE (tutti) — USA", "nyse"),
    "amex": ("AMEX (tutti) — USA", "amex"),
}


def _normalize(name: str) -> str:
    return name.lower().replace(" ", "").replace("&", "").replace(".", "")


def get_index_names() -> list[str]:
    names = list(HARDCODED_INDICES.keys()) + list(WIKI_INDICES.keys()) + list(FULL_EXCHANGE_LISTINGS.keys()) + list(EXCHANGE_SOURCES.keys())
    return sorted(names)


def get_display_name(key: str) -> str:
    key = _normalize(key)
    if key in HARDCODED_INDICES:
        return HARDCODED_INDICES[key][0]
    if key in WIKI_INDICES:
        return WIKI_INDICES[key][0]
    if key in FULL_EXCHANGE_LISTINGS:
        return FULL_EXCHANGE_LISTINGS[key][0]
    if key in EXCHANGE_SOURCES:
        return EXCHANGE_SOURCES[key][0]
    return key


def _fetch_full_wiki_listing(slug: str, col_name: str, suffix: str) -> Optional[list[str]]:
    url = f"https://en.wikipedia.org/wiki/{quote(slug)}"
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode()
        tables = pd.read_html(io.StringIO(html))
        tickers = []
        for df in tables:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [" ".join(str(c).strip() for c in col if str(c).strip()) for col in df.columns]
            match = [c for c in df.columns if col_name.lower() in str(c).lower()]
            if not match:
                continue
            col = match[0]
            for val in df[col]:
                if not isinstance(val, str):
                    continue
                t = val.strip()
                if not t:
                    continue
                t = t.replace("\xa0", " ").replace(" ", "")
                if ":" in t:
                    t = t.split(":", 1)[1].strip()
                if not t.endswith(suffix):
                    t += suffix
                tickers.append(t)
        if tickers:
            return tickers
        logger.warning(f"Nessuna colonna '{col_name}' trovata in nessuna tabella per {slug}")
        return None
    except Exception as e:
        logger.error(f"Errore scaricando {slug}: {e}")
        return None


def get_tickers_for_index(name: str) -> Optional[list[str]]:
    name = _normalize(name)

    if name in HARDCODED_INDICES:
        return HARDCODED_INDICES[name][1]

    if name in WIKI_INDICES:
        entry = WIKI_INDICES[name]
        display_name, wiki_slug, col_name, table_idx, suffix = entry[:5]
        exchange_map = entry[5] if len(entry) > 5 else {}
        try:
            url = f"https://en.wikipedia.org/wiki/{quote(wiki_slug, safe='/%')}"
            req = Request(url, headers={"User-Agent": _USER_AGENT})
            with urlopen(req, timeout=30) as resp:
                html = resp.read().decode()
            tables = pd.read_html(io.StringIO(html))
            df = tables[table_idx]

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [" ".join(str(c).strip() for c in col if str(c).strip()) for col in df.columns]

            match = [c for c in df.columns if col_name.lower() in str(c).lower()]
            if match:
                col = match[0]
                tickers = []
                for val in df[col]:
                    if not isinstance(val, str):
                        continue
                    t = val.strip()
                    if not t:
                        continue
                    t = t.replace("\xa0", " ")
                    t = t.replace(" ", "")
                    exchange = ""
                    if ":" in t:
                        parts = t.split(":", 1)
                        exchange = parts[0].strip()
                        t = parts[1].strip()
                    sfx = exchange_map.get(exchange, suffix)
                    if not t.endswith(sfx):
                        t += sfx
                    tickers.append(t)
                logger.info(f"Scaricati {len(tickers)} ticker da Wikipedia per {display_name}")
                return tickers
            else:
                logger.warning(f"Colonna '{col_name}' non trovata per {display_name}")
                for c in df.columns:
                    logger.info(f"  Colonna disponibile: {c}")
                return None
        except Exception as e:
            logger.error(f"Errore scaricando {display_name} da Wikipedia: {e}")
            return None

    if name in FULL_EXCHANGE_LISTINGS:
        display_name, slug, col_name, suffix = FULL_EXCHANGE_LISTINGS[name]
        return _fetch_full_wiki_listing(slug, col_name, suffix)

    if name in EXCHANGE_SOURCES:
        source_type = EXCHANGE_SOURCES[name][1]
        if source_type == "ftp":
            return _fetch_nasdaq_full()
        elif source_type == "nyse":
            return _fetch_other_listed("N")
        elif source_type == "amex":
            return _fetch_other_listed("A")

    return None
