"""
Knowledge Ingestion Script.

Run this once before starting the crew to populate IBM Db2 with the
airline enterprise knowledge base.

Usage:
    python scripts/ingest_knowledge.py              # incremental (skip existing)
    python scripts/ingest_knowledge.py --wipe       # wipe and re-ingest everything
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure src/ is importable when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logger import get_logger, configure_logging
from src.knowledge.ingestion_pipeline import IngestionPipeline

configure_logging()
log = get_logger("ingest_knowledge")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest airline knowledge documents into IBM Db2."
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        default=False,
        help="Delete all existing documents and vectors before ingesting.",
    )
    args = parser.parse_args()

    log.info("ingest_script.start", wipe=args.wipe)
    start = time.time()

    pipeline = IngestionPipeline()
    summary = pipeline.run(wipe_first=args.wipe)

    elapsed = round(time.time() - start, 1)
    log.info(
        "ingest_script.done",
        elapsed_seconds=elapsed,
        **summary,
    )

    print("\n" + "=" * 60)
    print("  Ingestion Complete")
    print("=" * 60)
    print(f"  Files processed   : {summary['file_count']}")
    print(f"  Chunks created    : {summary['chunk_count']}")
    print(f"  Documents stored  : {summary['doc_inserted']}")
    print(f"  Vectors stored    : {summary['vec_inserted']}")
    print(f"  Time elapsed      : {elapsed}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
