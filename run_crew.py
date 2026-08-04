#!/usr/bin/env python3
"""
run_crew.py — CLI entry point for the Airline Delay Management Assistant.

Usage:
    python run_crew.py
    python run_crew.py "Flight AI302 from Delhi to London is delayed due to heavy rain. What should we do?"

Optional env flags:
    LOG_COLOR=true python run_crew.py     # enable coloured output
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger("run_crew")

DEFAULT_QUERY = (
    "Flight AI302 from Delhi to London is delayed because of heavy rain. "
    "What should we do?"
)


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else DEFAULT_QUERY

    log.info("cli.start", python=sys.version.split()[0], query=query[:80])

    try:
        from src.crew.airline_crew import run
        run(query)
    except KeyboardInterrupt:
        print("\n\nAborted by user.", flush=True)
        sys.exit(0)
    except Exception as exc:
        log.error("cli.fatal_error", error=str(exc), exc_type=type(exc).__name__)
        print(f"\nFATAL: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
