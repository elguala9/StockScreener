#!/usr/bin/env python3
import argparse
import logging
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

from screener.config import ScreenerConfig
from screener.fetcher import fetch_all_tickers
from screener.filters import filter_stocks
from screener.indices import get_tickers_for_index, get_index_names
from screener.providers import get_provider, get_provider_names

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stock Screener - Analisi Fondamentale Automatica",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Esempi:\n"
            "  python main.py -e ftsemib --pe-min 8 --pe-max 15 --pb-max 1.5 --roe-min 10\n"
            "  python main.py -e sp500 --pe-max 20 --roe-min 15 --debt-equity-max 1.5\n"
            "  python main.py -t my_tickers.txt --pe-max 12 --fcf-yield-min 4\n"
        ),
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-e", "--exchange",
        help=f"Borsa/indice da analizzare. Opzioni: {', '.join(get_index_names())}",
    )
    group.add_argument(
        "-t", "--tickers",
        type=Path,
        help="File .txt con ticker personalizzati (uno per riga)",
    )

    parser.add_argument("--pe-min", type=float, help="P/E minimo")
    parser.add_argument("--pe-max", type=float, help="P/E massimo")
    parser.add_argument("--pb-min", type=float, help="P/B minimo")
    parser.add_argument("--pb-max", type=float, help="P/B massimo")
    parser.add_argument("--ps-min", type=float, help="P/S minimo")
    parser.add_argument("--ps-max", type=float, help="P/S massimo")
    parser.add_argument("--ev-ebitda-min", type=float, help="EV/EBITDA minimo")
    parser.add_argument("--ev-ebitda-max", type=float, help="EV/EBITDA massimo")
    parser.add_argument("--fcf-yield-min", type=float, help="FCF Yield minimo")
    parser.add_argument("--fcf-yield-max", type=float, help="FCF Yield massimo")
    parser.add_argument("--op-margin-min", type=float, help="Margine operativo minimo")
    parser.add_argument("--op-margin-max", type=float, help="Margine operativo massimo")
    parser.add_argument("--net-margin-min", type=float, help="Margine netto minimo")
    parser.add_argument("--net-margin-max", type=float, help="Margine netto massimo")
    parser.add_argument("--roe-min", type=float, help="ROE minimo")
    parser.add_argument("--roe-max", type=float, help="ROE massimo")
    parser.add_argument("--roic-min", type=float, help="ROIC minimo")
    parser.add_argument("--roic-max", type=float, help="ROIC massimo")
    parser.add_argument("--debt-equity-min", type=float, help="Debt/Equity minimo")
    parser.add_argument("--debt-equity-max", type=float, help="Debt/Equity massimo")
    parser.add_argument("--market-cap-min", type=float, help="Market Cap minimo (miliardi)")
    parser.add_argument("--market-cap-max", type=float, help="Market Cap massimo (miliardi)")
    parser.add_argument("--div-yield-min", type=float, help="Dividend Yield minimo")
    parser.add_argument("--div-yield-max", type=float, help="Dividend Yield massimo")
    parser.add_argument("--rev-growth-min", type=float, help="Crescita ricavi minima")
    parser.add_argument("--rev-growth-max", type=float, help="Crescita ricavi massima")

    parser.add_argument(
        "--provider",
        default="yahoo finance",
        help=f"Provider dati. Opzioni: {', '.join(get_provider_names())} (default: Yahoo Finance)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="API key per provider a pagamento (Finnhub, Alpha Vantage)",
    )

    parser.add_argument(
        "-o", "--output",
        default="output.csv",
        help="Percorso file CSV output (default: output.csv)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Numero di thread paralleli (default: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Secondi di pausa tra batch (default: 1)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Logging dettagliato (debug)",
    )

    return parser.parse_args()


def load_tickers_from_file(path: Path) -> list[str]:
    if not path.exists():
        logger.error(f"File non trovato: {path}")
        sys.exit(1)
    tickers = []
    with open(path, "r") as f:
        for line in f:
            t = line.strip()
            if t and not t.startswith("#"):
                tickers.append(t)
    if not tickers:
        logger.error(f"Il file {path} non contiene ticker validi")
        sys.exit(1)
    logger.info(f"Caricati {len(tickers)} ticker da {path}")
    return tickers


_CLI_TO_FIELD = {
    "op_margin_min": "operating_margin_min", "op_margin_max": "operating_margin_max",
    "div_yield_min": "dividend_yield_min", "div_yield_max": "dividend_yield_max",
    "rev_growth_min": "revenue_growth_min", "rev_growth_max": "revenue_growth_max",
}


def build_config(args: argparse.Namespace) -> ScreenerConfig:
    kwargs = {}
    for cfg_field in ScreenerConfig.field_names():
        cli_attr = next((k for k, v in _CLI_TO_FIELD.items() if v == cfg_field), cfg_field)
        val = getattr(args, cli_attr, None)
        if val is not None:
            kwargs[cfg_field] = float(val)
    return ScreenerConfig(**kwargs)


def show_progress(done: int, total: int):
    pct = done / total * 100
    bar_len = 30
    filled = int(bar_len * done / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  Progresso: |{bar}| {done}/{total} ({pct:.0f}%)", end="")
    if done == total:
        print()


def main():
    try:
        _main()
    except Exception:
        log_path = Path(__file__).resolve().parent / "error-log.txt"
        with open(log_path, "w") as f:
            f.write(traceback.format_exc())
        logger.error("Scan fallito — dettagli in error-log.txt")
        sys.exit(1)


def _main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = build_config(args)

    if args.exchange:
        name = args.exchange
        tickers = get_tickers_for_index(name)
        if tickers is None:
            logger.error(
                f"Indice '{name}' non riconosciuto. Opzioni: {', '.join(get_index_names())}"
            )
            sys.exit(1)
        logger.info(f"Indice: {name.upper()} ({len(tickers)} ticker)")
    else:
        tickers = load_tickers_from_file(args.tickers)

    provider = get_provider(args.provider, api_key=args.api_key)
    if provider is None:
        logger.error(
            f"Provider '{args.provider}' non valido. Opzioni: {', '.join(get_provider_names())}"
        )
        sys.exit(1)
    if provider.needs_api_key and not args.api_key:
        logger.error(
            f"Il provider '{provider.name}' richiede una API key. "
            f"Usa --api-key per fornirla."
        )
        sys.exit(1)

    if config.is_empty():
        logger.warning("Nessun filtro impostato. Verranno scaricati tutti i dati senza filtrare.")

    logger.info(f"Provider: {provider.name}")
    logger.info("Configurazione filtri:")
    for k, v in config.__dict__.items():
        if v is not None:
            logger.info(f"  {k}: {v}")

    logger.info(f"Avvio download dati ({args.max_workers} workers)...")
    start = time.time()

    stocks = fetch_all_tickers(
        provider,
        tickers,
        max_workers=args.max_workers,
        delay=args.delay,
        progress_callback=show_progress,
    )

    elapsed = time.time() - start
    fetched = len([s for s in stocks if not s.error])
    logger.info(
        f"Download completato in {elapsed:.1f}s. {fetched}/{len(tickers)} ticker con dati validi."
    )

    passed_list, failed_list = filter_stocks(stocks, config)

    logger.info(f"Risultati: {len(passed_list)} passano i filtri, {len(failed_list)} non passano")

    all_stocks = sorted(stocks, key=lambda s: (not s.passed, s.ticker))
    rows = [s.to_dict() for s in all_stocks]
    df = pd.DataFrame(rows)

    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    logger.info(f"CSV salvato: {args.output}")

    if passed_list:
        df_passed = pd.DataFrame([s.to_dict() for s in sorted(passed_list, key=lambda s: s.ticker)])
        passed_path = Path(args.output).stem + "_passati.csv"
        df_passed.to_csv(passed_path, index=False, encoding="utf-8-sig")
        logger.info(f"CSV (solo passati) salvato: {passed_path}")

    print(f"\n✅ Scan completato! {len(passed_list)} aziende trovate su {len(stocks)} analizzate.")
    if passed_list:
        print("Aziende che passano i filtri:")
        for s in sorted(passed_list, key=lambda s: s.ticker):
            print(f"  {s.ticker:12s} {s.name[:50]:50s} P/E: {_fmt(s.pe_ratio):>8s}  ROE: {_fmt(s.roe):>6s}")

    print(f"\nRisultati completi salvati in: {args.output}")


def _fmt(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


if __name__ == "__main__":
    main()
