# Stock Screener - Analisi Fondamentale Automatica

## Obiettivo

Applicazione Python da riga di comando che analizza un'intera borsa valori (es. FTSE MIB, S&P 500) e restituisce un CSV con tutte le aziende, i loro dati finanziari, e l'esito dei filtri impostati dall'utente.

I filtri si basano sui classici moltiplicatori di **valutazione relativa** e **valutazione assoluta** descritti nell'analisi fondamentale:

| Moltiplicatore | Cosa misura | Soglia tipica |
|---|---|---|
| P/E | Prezzo / Utili per azione | < media settore |
| P/B | Prezzo / Valore contabile | < 1 (sottovalutato) |
| P/S | Prezzo / Fatturato | < media settore |
| EV/EBITDA | Valore impresa / EBITDA | < competitor |
| FCF Yield | Free Cash Flow / Market Cap | > 3-5% |
| Margine Operativo | EBIT / Ricavi | stabile o in crescita |
| ROE | Utile netto / Patrimonio netto | > 10-15% |
| ROIC | NOPAT / Capitale investito | > WACC |
| Debt/Equity | Debiti / Patrimonio netto | < 1 |

## Architettura

```
stock-screener/
├── main.py                 # Entry point CLI (argparse)
├── requirements.txt        # Dipendenze (yfinance, pandas)
├── README.md               # Questo file
└── screener/
    ├── __init__.py
    ├── config.py            # Modello dei filtri (ScreenerConfig)
    ├── indices.py           # Lista ticker per borsa/indice
    ├── fetcher.py           # Download dati via yfinance (parallelo)
    ├── filters.py           # Applicazione filtri sui dati
    └── models.py            # Modello dati StockData
```

## Flusso di esecuzione

```
CLI (argparse)
    │
    ├─ Parametri filtri + Borsa
    │
    ▼
indices.py ──► Lista ticker per l'indice richiesto
    │
    ▼
fetcher.py ──► yfinance.Ticker per ogni simbolo (ThreadPoolExecutor)
    │               ↓
    │         StockData (modello dati)
    │
    ▼
filters.py ──► Confronta ogni StockData con ScreenerConfig
    │
    ▼
main.py ──► CSV con tutte le aziende + colonna "Supera Filtri"
```

## Installazione

**Dipendenze di sistema** (necessarie per la GUI):
- Fedora: `sudo dnf install python3-tkinter`
- Ubuntu/Debian: `sudo apt install python3-tk`
- Arch: `sudo pacman -S tk`
- Mac: già incluso con Python
- Windows: già incluso con Python

```bash
cd stock-screener
python3 -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

## Utilizzo

```bash
# Analisi FTSE MIB: P/E tra 8 e 15, P/B max 1.5, ROE minimo 10%
python main.py --exchange ftsemib --pe-min 8 --pe-max 15 --pb-max 1.5 --roe-min 10

# S&P 500 con filtri stringenti
python main.py --exchange sp500 --pe-max 20 --pb-max 3 --ev-ebitda-max 12 \
    --fcf-yield-min 3 --debt-equity-max 1.5 --roe-min 12

# NASDAQ completo (3300+ ticker)
python main.py --exchange nasdaq --pe-max 15 --roe-min 10

# Lista ticker personalizzata (file .txt, un ticker per riga)
python main.py --tickers my_list.txt --pe-max 15
```

## Parametri CLI

| Parametro | Alias | Descrizione |
|---|---|---|
| `--exchange` | `-e` | Borsa/indice: `ftsemib`, `sp500`, `nasdaq100`, `nasdaq` (completo), `nyse` (completo), `amex`, `dax40`, `cac40`, `ftse100`, `nikkei225` |
| `--tickers` | `-t` | File .txt con ticker personalizzati |
| `--pe-min` / `--pe-max` | | P/E minimo / massimo |
| `--pb-min` / `--pb-max` | | P/B minimo / massimo |
| `--ps-min` / `--ps-max` | | P/S minimo / massimo |
| `--ev-ebitda-min` / `--ev-ebitda-max` | | EV/EBITDA minimo / massimo |
| `--fcf-yield-min` / `--fcf-yield-max` | | FCF Yield minimo / massimo (%) |
| `--op-margin-min` / `--op-margin-max` | | Margine operativo min / max (%) |
| `--net-margin-min` / `--net-margin-max` | | Margine netto min / max (%) |
| `--roe-min` / `--roe-max` | | ROE minimo / massimo (%) |
| `--roic-min` / `--roic-max` | | ROIC minimo / massimo (%) |
| `--debt-equity-min` / `--debt-equity-max` | | Debt/Equity minimo / massimo |
| `--market-cap-min` / `--market-cap-max` | | Market Cap min / max (miliardi) |
| `--div-yield-min` / `--div-yield-max` | | Dividend Yield min / max (%) |
| `--rev-growth-min` / `--rev-growth-max` | | Crescita ricavi min / max (%) |
| `--provider` | | Provider dati: `Yahoo Finance`, `Finnhub`, `Alpha Vantage` (default: Yahoo) |
| `--api-key` | | API key per provider a pagamento (Finnhub, Alpha Vantage) |
| `--output` | `-o` | Percorso CSV output (default: output.csv) |
| `--max-workers` | | Thread paralleli (default: 5) |
| `--delay` | | Secondi di pausa tra batch (default: 1) |

## Provider dati

| Provider | API Key | Limiti free tier |
|---|---|---|
| **Yahoo Finance** | No | Rate limit, ~2-3 sec per ticker |
| **Finnhub** | [Registrati qui](https://finnhub.io/register) | 60 chiamate/minuto |
| **Alpha Vantage** | [Registrati qui](https://www.alphavantage.co/support/#api-key) | 5 chiamate/minuto, 500/giorno |

```bash
# Con Finnhub (più veloce di Yahoo)
python main.py -e sp500 --pe-max 15 --provider finnhub --api-key LA_TUA_KEY

# Con Alpha Vantage
python main.py -e ftsemib --pe-max 15 --provider "alpha vantage" --api-key LA_TUA_KEY
```

## Output CSV

Il CSV include **tutte** le aziende analizzate con i valori precisi, più una colonna `Supera Filtri` (True/False) e `Motivazioni` (dettaglio esito per ogni filtro).

## Interfaccia Grafica

```bash
python gui.py
```

L'interfaccia offre:
- Selezione borsa/indice da menù a tendina
- Selezione provider dati (Yahoo Finance, Finnhub, Alpha Vantage)
- Campo API Key abilitato automaticamente per provider che lo richiedono
- Tutti i filtri con campi min/max organizzati per gruppi (Valutazione, Redditività, Efficienza, Solidità, Altro)
- Pulsante "Sfoglia..." per scegliere dove salvare il CSV
- Barra di progresso durante lo scan
- Tabella risultati con righe verdi per le aziende che superano i filtri
- Salvataggio automatico CSV completo + CSV solo passati

## Prossimi sviluppi

- Salvataggio configurazioni filtri in JSON
- Backtesting storico dei filtri
- Analisi DCF integrata
- Notifiche automatiche via email/Telegram
