import argparse
import os
import logging
import sys
import time

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from backend.whatsapp_client import process_outbox
else:
    from .whatsapp_client import process_outbox

logger = logging.getLogger(__name__)


def run_worker(batch: int = 50, interval: int = 30, once: bool = False) -> int:
    processed_total = 0

    while True:
        processed = process_outbox(batch=batch)
        processed_total += processed
        logger.info("Outbox processata: %s messaggi", processed)

        if once:
            return processed_total

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker per processare la coda WhatsApp")
    parser.add_argument("--batch", type=int, default=50, help="Numero massimo di messaggi per ciclo")
    parser.add_argument("--interval", type=int, default=30, help="Secondi tra un ciclo e l'altro")
    parser.add_argument("--once", action="store_true", help="Esegui un solo ciclo e termina")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    total = run_worker(batch=args.batch, interval=args.interval, once=args.once)
    logger.info("Worker terminato. Messaggi processati: %s", total)


if __name__ == "__main__":
    main()
