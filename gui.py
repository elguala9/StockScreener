#!/usr/bin/env python3
import json
import logging
import queue
import threading
import traceback
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from datetime import datetime

import pandas as pd

from screener.config import ScreenerConfig
from screener.fetcher import fetch_all_tickers
from screener.filters import filter_stocks
from screener.indices import get_index_names, get_tickers_for_index, get_display_name
from screener.providers import get_provider, get_provider_names
from screener.models import StockData

logger = logging.getLogger(__name__)

TEMP_DIR = Path.cwd() / "temp"


def _safe_float_from_str(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

_SHORT_TO_LONG = {
    "pe": "pe", "pb": "pb", "ps": "ps", "ev_ebitda": "ev_ebitda",
    "fcf_yield": "fcf_yield", "op_margin": "operating_margin",
    "net_margin": "net_margin", "roe": "roe", "roic": "roic",
    "debt_equity": "debt_equity", "market_cap": "market_cap",
    "div_yield": "dividend_yield", "rev_growth": "revenue_growth",
}


def _cache_filename(exchange_key: str, provider_name: str, dt_str: str) -> str:
    safe_provider = provider_name.replace(" ", "+")
    safe_dt = dt_str.replace(" ", "T")
    return f"{exchange_key}_{safe_provider}_{safe_dt}.csv"


def _parse_cache_filename(filename: str) -> tuple[str, str, str] | None:
    stem = filename.replace(".csv", "")
    parts = stem.split("_", 2)
    if len(parts) != 3:
        return None
    exchange_key, provider_safe, dt_safe = parts
    provider_name = provider_safe.replace("+", " ")
    dt_part = dt_safe.replace("T", " ")
    try:
        datetime.strptime(dt_part, "%Y-%m-%d %H%M")
    except ValueError:
        return None
    return exchange_key, provider_name, dt_part


def _save_cache(stocks: list[StockData], exchange_key: str, provider_name: str, dt_str: str) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    filename = _cache_filename(exchange_key, provider_name, dt_str)
    path = TEMP_DIR / filename
    skip = {"passed", "reasons"}
    rows = [{k: v for k, v in asdict(s).items() if k not in skip} for s in stocks]
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _load_cache(exchange_key: str, provider_name: str, dt_str: str) -> list[StockData] | None:
    filename = _cache_filename(exchange_key, provider_name, dt_str)
    path = TEMP_DIR / filename
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    stocks = []
    for _, row in df.iterrows():
        kwargs = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                kwargs[col] = None
            elif col in ("ticker", "name", "sector", "industry", "error"):
                kwargs[col] = str(v)
            else:
                try:
                    kwargs[col] = float(v)
                except (ValueError, TypeError):
                    kwargs[col] = None
        stocks.append(StockData(**kwargs))
    return stocks


def _list_available_caches() -> list[tuple[str, str, str]]:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in TEMP_DIR.glob("*.csv"):
        parsed = _parse_cache_filename(f.name)
        if parsed:
            results.append(parsed)
    return sorted(results, key=lambda x: x[2], reverse=True)


class StockScreenerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Stock Screener - Analisi Fondamentale")
        self.root.geometry("1100x750")
        self._progress_queue: queue.Queue = queue.Queue()
        self._scanning = False
        self._setup_ui()
        self._poll_progress()

    def _setup_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        self._build_top_bar(main)
        self._build_filter_area(main)
        self._build_action_area(main)
        self._build_results_area(main)

    def _build_top_bar(self, parent):
        frame = ttk.LabelFrame(parent, text="Configurazione", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="Borsa / Indice:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.exchange_map = {get_display_name(k): k for k in get_index_names()}
        self.exchange_var = tk.StringVar()
        self.exchange_combo = ttk.Combobox(
            frame, textvariable=self.exchange_var,
            values=sorted(self.exchange_map.keys()),
            state="readonly", width=35,
        )
        self.exchange_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

        ttk.Label(frame, text="Provider:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(4, 0))
        self.provider_var = tk.StringVar(value="Yahoo Finance")
        self.provider_combo = ttk.Combobox(
            frame, textvariable=self.provider_var,
            values=get_provider_names(),
            state="readonly", width=20,
        )
        self.provider_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 20), pady=(4, 0))
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        ttk.Label(frame, text="API Key:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5), pady=(4, 0))
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(frame, textvariable=self.api_key_var, width=30, show="*")
        self.api_key_entry.grid(row=1, column=3, sticky=tk.W, padx=(0, 5), pady=(4, 0))
        self.api_key_entry.config(state=tk.DISABLED)

        ttk.Label(frame, text="File CSV output:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(4, 0))
        self.output_var = tk.StringVar(value="output.csv")
        self.output_entry = ttk.Entry(frame, textvariable=self.output_var, width=30)
        self.output_entry.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=(0, 5), pady=(4, 0))
        ttk.Button(frame, text="Sfoglia...", command=self._browse_output).grid(row=2, column=3, pady=(4, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=3, column=0, columnspan=4, sticky=tk.EW, pady=(4, 2))

        self.use_cache_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Usa cache",
                        variable=self.use_cache_var).grid(
            row=4, column=0, sticky=tk.W, padx=(0, 5), pady=(2, 0))

        ttk.Label(frame, text="Cache disponibili:").grid(row=4, column=1, sticky=tk.W, padx=(0, 5), pady=(2, 0))
        self.cache_file_var = tk.StringVar()
        self.cache_file_combo = ttk.Combobox(
            frame, textvariable=self.cache_file_var,
            values=[], state="readonly", width=50,
        )
        self.cache_file_combo.grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=(0, 5), pady=(2, 0))
        self.cache_file_combo.bind("<<ComboboxSelected>>", self._on_cache_file_select)

        self._refresh_cache_lists()

    def _on_provider_change(self, event=None):
        name = self.provider_var.get()
        p = get_provider(name, api_key="dummy")
        if p and p.needs_api_key:
            self.api_key_entry.config(state=tk.NORMAL)
        else:
            self.api_key_entry.config(state=tk.DISABLED)
            self.api_key_var.set("")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _refresh_cache_lists(self):
        caches = _list_available_caches()

        display_names = [
            f"{exch} - {prov} - {dt}"
            for exch, prov, dt in caches
        ]
        self._all_caches = list(zip(caches, display_names))
        if hasattr(self, "cache_file_combo"):
            self.cache_file_combo["values"] = display_names

    def _on_cache_file_select(self, event=None):
        selected = self.cache_file_var.get()
        if not selected:
            return
        for (exch, prov, dt), display in self._all_caches:
            if display == selected:
                display_name = get_display_name(exch)
                if display_name in self.exchange_map:
                    self.exchange_var.set(display_name)
                if prov in get_provider_names():
                    self.provider_var.set(prov)
                    self._on_provider_change()
                break

    def _build_filter_area(self, parent):
        frame = ttk.LabelFrame(parent, text="Filtri", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        self._filter_entries = {}

        groups = [
            ("Valutazione", ["pe", "pb", "ps", "ev_ebitda"]),
            ("Redditività", ["fcf_yield", "op_margin", "net_margin"]),
            ("Efficienza", ["roe", "roic"]),
            ("Solidità", ["debt_equity"]),
            ("Altro", ["market_cap", "div_yield", "rev_growth"]),
        ]

        col = 0
        for group_name, fields in groups:
            g = ttk.LabelFrame(frame, text=group_name, padding=8)
            g.grid(row=0, column=col, sticky=tk.NSEW, padx=4)
            frame.columnconfigure(col, weight=1)

            labels = {
                "pe": "P/E", "pb": "P/B", "ps": "P/S", "ev_ebitda": "EV/EBITDA",
                "fcf_yield": "FCF Yield %", "op_margin": "Margine Op. %",
                "net_margin": "Margine Netto %", "roe": "ROE %", "roic": "ROIC %",
                "debt_equity": "Debt/Equity", "market_cap": "Market Cap (B$)",
                "div_yield": "Dividend Yield %", "rev_growth": "Crescita Ricavi %",
            }

            for i, fld in enumerate(fields):
                lbl = labels.get(fld, fld)
                ttk.Label(g, text=lbl).grid(row=i * 2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))

                min_var = tk.StringVar()
                max_var = tk.StringVar()

                ttk.Label(g, text="min:", width=3).grid(row=i * 2 + 1, column=0, sticky=tk.W)
                e_min = ttk.Entry(g, textvariable=min_var, width=10)
                e_min.grid(row=i * 2 + 1, column=1, sticky=tk.W, padx=(0, 4))

                ttk.Label(g, text="max:", width=3).grid(row=i * 2 + 1, column=2, sticky=tk.W)
                e_max = ttk.Entry(g, textvariable=max_var, width=10)
                e_max.grid(row=i * 2 + 1, column=3, sticky=tk.W)

                self._filter_entries[fld] = (min_var, max_var)

            col += 1

        self._set_defaults()

    def _set_defaults(self):
        json_path = Path(__file__).resolve().parent / "default.json"
        if json_path.exists():
            try:
                with open(json_path) as f:
                    defaults = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Errore leggendo {json_path}: {e}")
                defaults = {}
            for fld, bounds in defaults.items():
                if isinstance(bounds, dict) and fld in self._filter_entries:
                    min_var, max_var = self._filter_entries[fld]
                    lo = bounds.get("min")
                    hi = bounds.get("max")
                    if lo is not None:
                        min_var.set(str(lo))
                    if hi is not None:
                        max_var.set(str(hi))
        else:
            hardcoded = {
                "pe": (None, "15"),
                "pb": (None, "1.5"),
                "ps": (None, "2"),
                "ev_ebitda": (None, "10"),
                "fcf_yield": ("3", None),
                "op_margin": ("5", None),
                "roe": ("10", None),
                "roic": ("8", None),
                "debt_equity": (None, "1"),
                "market_cap": ("0.5", None),
            }
            for fld, (lo, hi) in hardcoded.items():
                if fld in self._filter_entries:
                    min_var, max_var = self._filter_entries[fld]
                    if lo is not None:
                        min_var.set(lo)
                    if hi is not None:
                        max_var.set(hi)

    def _export_config(self):
        data = {}
        for fld, (min_var, max_var) in self._filter_entries.items():
            lo = _safe_float_from_str(min_var.get())
            hi = _safe_float_from_str(max_var.get())
            data[fld] = {"min": lo, "max": hi}

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
        except OSError as e:
            messagebox.showerror("Errore", f"Impossibile scrivere {path}: {e}")
            return
        messagebox.showinfo("Esportato", f"Configurazione esportata in {path}")

    def _import_config(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Errore", f"Impossibile leggere {path}: {e}")
            return

        for fld, (min_var, max_var) in self._filter_entries.items():
            if fld in data and isinstance(data[fld], dict):
                bounds = data[fld]
                lo = bounds.get("min")
                hi = bounds.get("max")
                min_var.set(str(lo) if lo is not None else "")
                max_var.set(str(hi) if hi is not None else "")
            else:
                min_var.set("")
                max_var.set("")

        messagebox.showinfo("Importato", f"Configurazione importata da {path}")

    def _export_search(self):
        data = {
            "exchange": self.exchange_var.get(),
            "provider": self.provider_var.get(),
            "api_key": self.api_key_var.get(),
            "output_path": self.output_var.get(),
            "filters": {},
        }
        for fld, (min_var, max_var) in self._filter_entries.items():
            lo = _safe_float_from_str(min_var.get())
            hi = _safe_float_from_str(max_var.get())
            data["filters"][fld] = {"min": lo, "max": hi}

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
        except OSError as e:
            messagebox.showerror("Errore", f"Impossibile scrivere {path}: {e}")
            return
        messagebox.showinfo("Esportato", f"Ricerca esportata in {path}")

    def _import_search(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Errore", f"Impossibile leggere {path}: {e}")
            return

        exchange = data.get("exchange", "")
        if exchange in self.exchange_map:
            self.exchange_var.set(exchange)

        provider = data.get("provider", "")
        if provider in get_provider_names():
            self.provider_var.set(provider)
            self._on_provider_change()

        self.api_key_var.set(data.get("api_key", ""))

        output_path = data.get("output_path", "")
        if output_path:
            self.output_var.set(output_path)

        filters = data.get("filters", {})
        for fld, (min_var, max_var) in self._filter_entries.items():
            if fld in filters and isinstance(filters[fld], dict):
                bounds = filters[fld]
                lo = bounds.get("min")
                hi = bounds.get("max")
                min_var.set(str(lo) if lo is not None else "")
                max_var.set(str(hi) if hi is not None else "")
            else:
                min_var.set("")
                max_var.set("")

        messagebox.showinfo("Importato", f"Ricerca importata da {path}")

    def _build_action_area(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 10))

        self.scan_btn = ttk.Button(frame, text="Avvia Scan", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(frame, text="Export Conf", command=self._export_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame, text="Import Conf", command=self._import_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame, text="Export Search", command=self._export_search).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame, text="Import Search", command=self._import_search).pack(side=tk.LEFT, padx=(0, 10))

        self.progress = ttk.Progressbar(frame, length=400, mode="determinate")
        self.progress.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(frame, textvariable=self.status_var).pack(side=tk.LEFT)

    def _build_results_area(self, parent):
        frame = ttk.LabelFrame(parent, text="Risultati", padding=5)
        frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Ticker", "Nome", "Prezzo", "P/E", "P/B", "P/S", "EV/EBITDA",
                "FCF Yield %", "Margine Op. %", "ROE %", "ROIC %",
                "Debt/Equity", "Supera Filtri", "Motivazioni")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        widths = {
            "Ticker": 70, "Nome": 200, "Prezzo": 60, "P/E": 55, "P/B": 55,
            "P/S": 55, "EV/EBITDA": 70, "FCF Yield %": 70, "Margine Op. %": 70,
            "ROE %": 55, "ROIC %": 55, "Debt/Equity": 70,
            "Supera Filtri": 90, "Motivazioni": 300,
        }
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths.get(c, 80), minwidth=50, anchor=tk.W if c == "Nome" else tk.CENTER)

        self.result_label = ttk.Label(frame, text="")
        self.result_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))

    def _build_config_from_ui(self) -> ScreenerConfig:
        kwargs = {}
        for short, (min_var, max_var) in self._filter_entries.items():
            lo = _safe_float_from_str(min_var.get())
            hi = _safe_float_from_str(max_var.get())
            long_name = _SHORT_TO_LONG.get(short, short)
            if lo is not None:
                kwargs[f"{long_name}_min"] = lo
            if hi is not None:
                kwargs[f"{long_name}_max"] = hi
        return ScreenerConfig(**kwargs)

    def _start_scan(self):
        if self._scanning:
            return

        display_name = self.exchange_var.get().strip()
        if not display_name:
            messagebox.showwarning("Attenzione", "Seleziona una borsa/indice.")
            return

        exchange_key = self.exchange_map.get(display_name, display_name)
        tickers = get_tickers_for_index(exchange_key)
        if not tickers:
            messagebox.showerror("Errore", f"Nessun ticker trovato per '{display_name}'.")
            return

        if len(tickers) > 500:
            ok = messagebox.askyesno(
                "Conferma",
                f"{display_name} ha {len(tickers)} ticker.\n"
                f"Ci vorranno circa {len(tickers) // 60} minuti.\n\n"
                "Vuoi continuare?"
            )
            if not ok:
                return

        provider_name = self.provider_var.get()
        api_key = self.api_key_var.get().strip()
        provider = get_provider(provider_name, api_key=api_key)
        if provider is None:
            msg = f"Provider '{provider_name}' non disponibile."
            if api_key == "":
                msg += f"\n\n{provider_name} richiede una API key."
            messagebox.showerror("Errore", msg)
            return

        config = self._build_config_from_ui()

        self._scanning = True
        self.scan_btn.config(state=tk.DISABLED, text="Scan in corso...")
        self.progress["value"] = 0
        self.status_var.set("Avvio scan...")
        self.tree.delete(*self.tree.get_children())
        self.result_label.config(text="")

        t = threading.Thread(
            target=self._run_scan,
            args=(display_name, exchange_key, tickers, config, provider),
            daemon=True,
        )
        t.start()

    def _run_scan(self, display_name: str, exchange_key: str, tickers: list[str],
                  config: ScreenerConfig, provider):
        try:
            dt_str = datetime.now().strftime("%Y-%m-%d %H%M")
            provider_name = provider.name

            use_cache = self.use_cache_var.get()
            stocks = None
            if use_cache:
                cached_file = self.cache_file_var.get()
                if cached_file:
                    for (exch, prov, dt), display in self._all_caches:
                        if display == cached_file and exch == exchange_key and prov == provider_name:
                            dt_str = dt
                            break
                stocks = _load_cache(exchange_key, provider_name, dt_str)
                if stocks is not None:
                    self._progress_queue.put(("status", f"Caricati {len(stocks)} ticker da cache ({date_str})"))

            if stocks is None:
                self._progress_queue.put(("status", f"Download {display_name} ({len(tickers)} ticker) con {provider_name}..."))

                def progress_cb(done, total):
                    self._progress_queue.put(("progress", done, total))

                stocks = fetch_all_tickers(
                    provider, tickers, max_workers=5, delay=1.0, progress_callback=progress_cb,
                )

                _save_cache(stocks, exchange_key, provider_name, dt_str)

                self.root.after(0, self._refresh_cache_lists)

            self._progress_queue.put(("status", "Applicazione filtri..."))
            passed_list, failed_list = filter_stocks(stocks, config)

            all_stocks = sorted(stocks, key=lambda s: (not s.passed, s.ticker))
            rows = [s.to_dict() for s in all_stocks]
            df = pd.DataFrame(rows)

            output_path = self.output_var.get().strip() or "output.csv"
            df.to_csv(output_path, index=False, encoding="utf-8-sig")

            passed_path = Path(output_path).stem + "_passati.csv"
            if passed_list:
                df_passed = pd.DataFrame([s.to_dict() for s in sorted(passed_list, key=lambda s: s.ticker)])
                df_passed.to_csv(passed_path, index=False, encoding="utf-8-sig")

            self._progress_queue.put((
                "done", stocks, passed_list, failed_list, output_path, passed_path
            ))

        except Exception as e:
            log_path = Path(__file__).resolve().parent / "error-log.txt"
            with open(log_path, "w") as f:
                f.write(traceback.format_exc())
            logger.error("Scan fallito%sDettagli in error-log.txt", " — " if e.__traceback__ else ": ")
            self._progress_queue.put(("error", str(e)))

    def _poll_progress(self):
        try:
            while True:
                msg = self._progress_queue.get_nowait()
                self._handle_progress(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_progress)

    def _handle_progress(self, msg):
        tag = msg[0]

        if tag == "progress":
            _, done, total = msg
            pct = int(done / total * 100) if total > 0 else 0
            self.progress["value"] = pct
            self.status_var.set(f"Scaricati {done}/{total} ({pct}%)")

        elif tag == "status":
            self.status_var.set(msg[1])

        elif tag == "done":
            _, stocks, passed_list, failed_list, output_path, passed_path = msg
            self._scanning = False
            self.scan_btn.config(state=tk.NORMAL, text="Avvia Scan")
            self.progress["value"] = 100

            fetched = len([s for s in stocks if not s.error])
            status = (
                f"Completato! {len(passed_list)} aziende su {fetched} analizzate "
                f"superano i filtri. CSV: {output_path}"
            )
            self.status_var.set(status)
            self.result_label.config(
                text=f"{len(passed_list)} aziende trovate su {len(stocks)} analizzate "
                     f"(di cui {len(stocks) - fetched} senza dati)"
            )

            self.tree.delete(*self.tree.get_children())

            def _row_vals(s, passed):
                return (
                    s.ticker, s.name[:60], self._fmt(s.current_price),
                    self._fmt(s.pe_ratio), self._fmt(s.pb_ratio),
                    self._fmt(s.ps_ratio), self._fmt(s.ev_ebitda),
                    self._fmt(s.fcf_yield), self._fmt(s.operating_margin),
                    self._fmt(s.roe), self._fmt(s.roic),
                    self._fmt(s.debt_equity), "SI" if passed else "NO",
                    "; ".join(s.reasons[:3]) + ("..." if len(s.reasons) > 3 else ""),
                )

            for s in sorted(passed_list, key=lambda x: x.ticker):
                self.tree.insert("", tk.END, values=_row_vals(s, True), tags=("pass",))

            for s in sorted(failed_list, key=lambda x: x.ticker):
                if not s.error:
                    self.tree.insert("", tk.END, values=_row_vals(s, False))

            self.tree.tag_configure("pass", background="#e8f5e9")

            if passed_list:
                messagebox.showinfo(
                    "Scan completato",
                    f"{len(passed_list)} aziende superano i filtri.\n\n"
                    f"CSV salvato: {output_path}\n"
                    f"Solo passati: {passed_path}",
                )

        elif tag == "error":
            self._scanning = False
            self.scan_btn.config(state=tk.NORMAL, text="Avvia Scan")
            messagebox.showerror("Errore", msg[1])
            self.status_var.set("Errore durante lo scan")

    @staticmethod
    def _fmt(val, decimals=2):
        if val is None:
            return ""
        if not isinstance(val, (int, float)):
            return str(val)
        return f"{val:.{decimals}f}"

    def run(self):
        self.root.mainloop()


def main():
    logging.basicConfig(level=logging.WARNING)
    app = StockScreenerGUI()
    app.run()


if __name__ == "__main__":
    main()
