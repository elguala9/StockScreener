import urllib.request
import urllib.parse
import urllib.error
import pandas as pd
from io import StringIO
import time

def flatten_col(col):
    if isinstance(col, tuple):
        for c in reversed(col):
            s = str(c).strip().lower()
            if s and s not in ('', 'nan'):
                return s
    return str(col).strip().lower()

SLUG_GROUPS = [
    (["SSE_50_Index"], "China SSE 50"),
    (["CSI_300"], "China CSI 300"),
    (["SZSE_Component_Index"], "China Shenzhen"),
    (["CSI_100"], "China CSI 100"),
    (["S&P_Asia_50"], "S&P Asia 50"),
    (["Índice_de_Precios_y_Cotizaciones", "BMV_IPC", "S&P/BMV_IPC", "IPC_(Index)"], "Mexico IPC"),
    (["KSE_100_Index", "KSE_100"], "Pakistan KSE 100"),
    (["KSE_30_Index"], "Pakistan KSE 30"),
    (["ATX_(stock_market_index)", "ATX_index", "Austrian_Traded_Index"], "Austria ATX"),
    (["PX_Index"], "Czech PX"),
    (["BUX"], "Hungary BUX"),
    (["BET_10"], "Romania BET"),
    (["CROBEX"], "Croatia CROBEX"),
    (["SBITOP"], "Slovenia SBITOP"),
    (["SAX_Index", "SAX_(stock_market_index)"], "Slovakia SAX"),
    (["OMX_Riga"], "Latvia OMX Riga"),
    (["OMX_Vilnius"], "Lithuania OMX Vilnius"),
    (["OMX_Tallinn"], "Estonia OMX Tallinn"),
    (["Tadawul_All_Share"], "Saudi Arabia Tadawul"),
    (["TA-35", "TA_35", "TA_125"], "Israel TA-35"),
    (["FTSE_Straits_Times_Index"], "Singapore FTSE STI"),
    (["KOSPI", "KOSPI_200"], "South Korea KOSPI"),
    (["MOEX_Russia"], "Russia MOEX"),
    (["BIST_100"], "Turkey BIST 100"),
]

COLUMN_NAMES = {"ticker", "symbol", "code", "mnem code", "ticker symbol",
    "company code", "constituent", "component", "mnemonic",
    "ticker_code", "stock_code"}

for variants, label in SLUG_GROUPS:
    html = None
    slug = variants[0]
    for attempt in variants:
        url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(attempt, safe='')
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
            slug = attempt
            break
        except urllib.error.HTTPError as e:
            if e.code == 404 and len(variants) > 1:
                continue
            if e.code == 404:
                print(f"{slug}: 404 NOT FOUND")
            else:
                print(f"{slug}: HTTP {e.code}")
            break
        except Exception as e:
            if len(variants) > 1:
                continue
            print(f"{slug}: FETCH ERROR {e}")
            break
    else:
        print(f"{slug}: ALL VARIANTS 404")
        continue
    if html is None:
        continue

    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        print(f"{slug}: PARSE ERROR {e}")
        continue

    found = False
    for i, tbl in enumerate(tables):
        cols = tbl.columns
        norm_cols = set()
        col_index_map = {}
        if isinstance(cols, pd.MultiIndex):
            for j, col in enumerate(cols):
                flat = flatten_col(col)
                norm_cols.add(flat)
                col_index_map[flat] = j
        else:
            for j, col in enumerate(cols):
                flat = str(col).strip().lower()
                norm_cols.add(flat)
                col_index_map[flat] = j

        match = norm_cols & COLUMN_NAMES
        if match:
            matched_name = sorted(match)[0]
            col_idx = col_index_map[matched_name]
            vals = tbl.iloc[:, col_idx].dropna().astype(str).str.strip()
            vals = vals[vals != ''].tolist()
            vals = [v for v in vals if not v.startswith('vte')][:3]
            print(f"{slug}: table index={i}, matched column=\"{matched_name}\", sample={vals}")
            found = True
            break
    if not found:
        print(f"{slug}: NOT FOUND")

    time.sleep(0.5)
