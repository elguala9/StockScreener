import urllib.request, urllib.parse, pandas as pd
from io import StringIO

slug = "KSE_100_Index"
url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(slug, safe='')
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode("utf-8")
tables = pd.read_html(StringIO(html))
tbl = tables[2]
print(f"Table 2 shape: {tbl.shape}")
print(f"Columns: {tbl.columns.tolist()}")
print(tbl.head(10).to_string())
print("\n---\n")

tbl = tables[0]
print(f"Table 0 shape: {tbl.shape}")
print(f"Columns: {tbl.columns.tolist()}")
print(tbl.head(10).to_string())
