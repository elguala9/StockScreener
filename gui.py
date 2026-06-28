#!/usr/bin/env python3
import json
import logging
import queue
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import pandas as pd

from screener.config import ScreenerConfig, SHORT_TO_LONG
from screener.fetcher import fetch_all_tickers
from screener.filters import filter_stocks
from screener.indices import get_index_names, get_tickers_for_index, get_display_name
from screener.providers import get_provider, get_provider_names

logger = logging.getLogger(__name__)


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
            with open(json_path) as f:
                defaults = json.load(f)
            for fld, bounds in defaults.items():
                if fld in self._filter_entries:
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

    def _create_dummy_json(self):
        dummy = {fld: {"min": 0, "max": 999} for fld in self._filter_entries}
        path = Path(__file__).resolve().parent / "dummy_json"
        with open(path, "w") as f:
            json.dump(dummy, f, indent=4)
        messagebox.showinfo("Dummy Default", f"Creato {path}")

    def _export_config(self):
        data = {}
        for fld, (min_var, max_var) in self._filter_entries.items():
            lo_s = min_var.get().strip()
            hi_s = max_var.get().strip()
            lo = float(lo_s) if lo_s else None
            hi = float(hi_s) if hi_s else None
            data[fld] = {"min": lo, "max": hi}

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
        messagebox.showinfo("Esportato", f"Configurazione esportata in {path}")

    def _import_config(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path) as f:
            data = json.load(f)

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

    def _build_action_area(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 10))

        self.scan_btn = ttk.Button(frame, text="Avvia Scan", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(frame, text="Export Conf", command=self._export_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame, text="Import Conf", command=self._import_config).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(frame, text="Dummy Default", command=self._create_dummy_json).pack(side=tk.LEFT, padx=(0, 10))

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
        data = {}
        for short in SHORT_TO_LONG:
            min_v, max_v = self._filter_entries.get(short, (None, None))
            lo = float(min_v.get()) if min_v.get().strip() else None
            hi = float(max_v.get()) if max_v.get().strip() else None
            data[short] = (lo, hi)
        return ScreenerConfig.from_filter_dict(data)

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
            args=(display_name, tickers, config, provider),
            daemon=True,
        )
        t.start()

    def _run_scan(self, display_name: str, tickers: list[str], config: ScreenerConfig, provider):
        try:
            self._progress_queue.put(("status", f"Download {display_name} ({len(tickers)} ticker) con {provider.name}..."))

            def progress_cb(done, total):
                self._progress_queue.put(("progress", done, total))

            stocks = fetch_all_tickers(
                provider, tickers, max_workers=5, delay=1.0, progress_callback=progress_cb,
            )

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
            pct = int(done / total * 100)
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
        return f"{val:.{decimals}f}"

    def run(self):
        self.root.mainloop()


def main():
    logging.basicConfig(level=logging.WARNING)
    app = StockScreenerGUI()
    app.run()


if __name__ == "__main__":
    main()
