#!/usr/bin/env python3
"""
Pure-Python traffic data collector (replaces traffic_collector.R + .sh).

Drop-in replacement with built-in scheduling.  Produces the same
GeoPackage output that the R ``hereR::flow()`` collector produces.

Usage:
    # Collect once for all cities
    python traffic_collector.py --once

    # Continuous collection every 15 min (replaces cron)
    python traffic_collector.py --interval 900

    # Specific cities only
    python traffic_collector.py --city smg bdg --once

    # With explicit API key
    python traffic_collector.py --api-key YOUR_KEY --once

Environment variables:
    HERE_API_KEY   – HERE platform API key (preferred over --api-key)
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running from the repo root without installing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trafficpipeline.collector import collect_all, collect_single  # noqa: E402
from trafficpipeline.config import CITIES, TIMEZONE  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d – shutting down after current cycle …", signum)
    _shutdown = True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect traffic flow data from the HERE Traffic API v7",
    )
    parser.add_argument(
        "--city",
        nargs="+",
        choices=list(CITIES.keys()),
        default=None,
        help="City codes to collect (default: all)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("HERE_API_KEY"),
        help="HERE API key (default: $HERE_API_KEY env var)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=900,
        help="Seconds between collection cycles (default: 900 = 15 min)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Collect once and exit (for cron-based scheduling)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override base output directory",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Append log output to this file",
    )
    args = parser.parse_args()

    # Validate API key
    if not args.api_key:
        parser.error(
            "No API key provided. Set HERE_API_KEY env var or use --api-key."
        )

    # Optional file logging
    if args.log_file:
        fh = logging.FileHandler(args.log_file)
        fh.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")
        )
        logging.getLogger().addHandler(fh)

    city_codes = args.city or list(CITIES.keys())
    city_names = ", ".join(CITIES[c]["name"] for c in city_codes)

    logger.info("=" * 60)
    logger.info("HERE Traffic Flow Collector (Python)")
    logger.info("Cities: %s", city_names)
    if args.once:
        logger.info("Mode: single collection")
    else:
        logger.info("Mode: continuous (every %ds)", args.interval)
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    cycle = 0
    while True:
        cycle += 1
        import pytz

        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        logger.info(
            "── Cycle %d ── %s ──",
            cycle,
            now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        )

        t0 = time.time()
        paths = collect_all(
            api_key=args.api_key,
            city_codes=city_codes,
            output_base=args.output_dir,
        )
        elapsed = time.time() - t0

        for p in paths:
            logger.info("  ✓ %s", p)

        logger.info(
            "Cycle %d complete: %d/%d cities in %.1fs",
            cycle,
            len(paths),
            len(city_codes),
            elapsed,
        )

        if args.once or _shutdown:
            break

        # Sleep until next cycle, checking for shutdown every second
        next_time = t0 + args.interval
        remaining = next_time - time.time()
        if remaining > 0:
            logger.info("Next collection in %ds …", int(remaining))
            while remaining > 0 and not _shutdown:
                time.sleep(min(remaining, 1.0))
                remaining = next_time - time.time()

        if _shutdown:
            break

    logger.info("Done.")


if __name__ == "__main__":
    main()
