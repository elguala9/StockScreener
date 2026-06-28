import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import StockData
from .providers import DataProvider

logger = logging.getLogger(__name__)


def fetch_all_tickers(
    provider: DataProvider,
    tickers: list[str],
    max_workers: int = 5,
    delay: float = 1.0,
    progress_callback=None,
) -> list[StockData]:
    results: list[StockData] = []
    total = len(tickers)
    batch_size = max_workers

    logger.info(
        f"Avvio fetch per {total} ticker con {max_workers} workers "
        f"(provider: {provider.name})"
    )

    for batch_start in range(0, total, batch_size):
        batch = tickers[batch_start : batch_start + batch_size]
        batch_results: list[StockData] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(provider.fetch_ticker, t): t for t in batch
            }
            for future in as_completed(future_map):
                try:
                    data = future.result()
                    batch_results.append(data)
                except Exception as e:
                    t = future_map[future]
                    batch_results.append(StockData(ticker=t, error=str(e)))
                    logger.debug(f"Errore in fetch per {t}: {e}")

        results.extend(batch_results)

        done = min(batch_start + batch_size, total)
        if progress_callback:
            progress_callback(done, total)

        if batch_start + batch_size < total:
            logger.debug(f"Pausa di {delay}s tra batch...")
            time.sleep(delay)

    return results
