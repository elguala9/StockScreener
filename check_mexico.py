import urllib.request
import urllib.parse
import pandas as pd
from io import StringIO

# Mexico IPC - need URL encoding for the accented characters
slug = "Índice_de_Precios_y_Cotizaciones"
url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(slug, safe='')
print(f"Fetching: {url}")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8")
    tables = pd.read_html(StringIO(html))
    print(f"Found {len(tables)} tables")
    for i, tbl in enumerate(tables):
        print(f"Table {i} columns: {list(tbl.columns)}")
except Exception as e:
    print(f"Error: {e}")
