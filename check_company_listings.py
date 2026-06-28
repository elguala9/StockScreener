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

COLUMN_NAMES = {"ticker", "symbol", "code", "mnem code", "ticker symbol",
    "company code", "constituent", "component", "mnemonic",
    "ticker_code", "stock_code"}

SLUG_GROUPS = [
    (["List_of_companies_listed_on_the_London_Stock_Exchange"], "London Stock Exchange"),
    (["List_of_companies_listed_on_the_Frankfurt_Stock_Exchange",
      "List_of_German_companies"], "Frankfurt Stock Exchange"),
    (["List_of_companies_listed_on_Euronext",
      "List_of_companies_on_Euronext",
      "Euronext_100"], "Euronext"),
    (["List_of_companies_listed_on_the_Tokyo_Stock_Exchange",
      "List_of_Japanese_companies"], "Tokyo Stock Exchange (Japan)"),
    (["List_of_companies_listed_on_the_Toronto_Stock_Exchange"], "Toronto Stock Exchange (Canada)"),
    (["List_of_companies_listed_on_the_Swiss_Exchange",
      "List_of_companies_listed_on_the_SIX_Swiss_Exchange",
      "List_of_Swiss_companies"], "Swiss Exchange"),
    (["List_of_companies_listed_on_the_Australian_Securities_Exchange",
      "List_of_Australian_companies"], "Australian Securities Exchange"),
    (["List_of_companies_listed_on_the_Hong_Kong_Stock_Exchange"], "Hong Kong Stock Exchange"),
    (["List_of_companies_listed_on_the_Bombay_Stock_Exchange",
      "List_of_companies_of_India"], "Bombay Stock Exchange (India)"),
    (["List_of_companies_listed_on_the_National_Stock_Exchange_of_India"], "NSE India"),
    (["List_of_companies_listed_on_the_Shanghai_Stock_Exchange",
      "List_of_companies_of_China"], "Shanghai Stock Exchange (China)"),
    (["List_of_companies_listed_on_the_Shenzhen_Stock_Exchange"], "Shenzhen Stock Exchange (China)"),
    (["List_of_companies_listed_on_the_Korea_Exchange",
      "List_of_Korean_companies"], "Korea Exchange (South Korea)"),
    (["List_of_companies_listed_on_the_Six_Swedish_Stock_Exchange",
      "List_of_companies_listed_on_the_Stockholm_Stock_Exchange",
      "List_of_Swedish_companies"], "Swedish/Six Stockholm Exchange"),
    (["Azioni_quotate_alla_Borsa_Italiana"], "Borsa Italiana (Italian Wikipedia)", True),
]

for entry in SLUG_GROUPS:
    if len(entry) == 3:
        variants, label, is_italian = entry
    else:
        variants, label = entry
        is_italian = False

    html = None
    slug = variants[0]
    for attempt in variants:
        if is_italian:
            url = "https://it.wikipedia.org/wiki/" + urllib.parse.quote(attempt, safe='')
        else:
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
            if e.code == 404:
                continue
            print(f"  {slug} ({label}): HTTP {e.code}")
            break
        except Exception as e:
            continue
    else:
        print(f"  {slug} ({label}): ALL VARIANTS 404")
        continue
    if html is None:
        continue

    try:
        tables = pd.read_html(StringIO(html))
    except ValueError as e:
        print(f"  {slug} ({label}): NO TABLES FOUND")
        continue
    except Exception as e:
        print(f"  {slug} ({label}): PARSE ERROR {e}")
        continue

    found_tables = []
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
            vals = vals[vals != '']
            nrows = len(vals)
            found_tables.append((i, matched_name, nrows))

    if found_tables:
        total_rows = sum(t[2] for t in found_tables)
        tables_detail = "; ".join(f"tbl[{t[0]}] col=\"{t[1]}\" rows={t[2]}" for t in found_tables)
        print(f"  {slug} ({label}): {len(found_tables)} table(s) with ticker: {tables_detail} (total rows={total_rows})")
    else:
        print(f"  {slug} ({label}): NOT FOUND")

    time.sleep(0.5)
