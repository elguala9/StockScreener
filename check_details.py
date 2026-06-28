import urllib.request
import urllib.parse
import pandas as pd
from io import StringIO

SLUGS = [
    "KSE_100_Index",
    "ATX_index",
    "Austrian_Traded_Index",
    "PX_Index",
    "BET_10",
    "SBITOP",
    "SAX_Index",
    "SAX_(stock_market_index)",
    "OMX_Riga",
    "OMX_Tallinn",
    "Tadawul_All_Share",
    "TA-35",
    "TA_35",
    "TA_125",
    "FTSE_Straits_Times_Index",
    "MOEX_Russia",
    "BIST_100",
    "KSE_100",
    "KSE_30_Index",
]

COLUMN_NAMES = {"ticker", "symbol", "code", "mnem code", "ticker symbol",
    "company code", "constituent", "component", "mnemonic", "ticker_code", "stock_code"}

for slug in SLUGS:
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(slug, safe='')
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"{slug}: 404")
            continue
        print(f"{slug}: HTTP {e.code}")
        continue
    except Exception as e:
        print(f"{slug}: {e}")
        continue

    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        print(f"{slug}: PARSE ERROR {e}")
        continue

    print(f"\n=== {slug} ({len(tables)} tables) ===")
    for i, tbl in enumerate(tables):
        cols = [str(c).strip() for c in tbl.columns]
        norm = {c.lower() for c in cols}
        match = norm & COLUMN_NAMES
        status = f"MATCH={match}" if match else ""
        print(f"  Table {i}: {cols[:8]} {'...' if len(cols)>8 else ''} {status}")
        if match:
            col_name = list(match)[0]
            for idx, c in enumerate(cols):
                if c.lower() == col_name:
                    sample = tbl.iloc[:, idx].dropna().astype(str).str.strip().tolist()
                    sample = [s for s in sample if s][:3]
                    print(f"    -> sample: {sample}")
                    break
