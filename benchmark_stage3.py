#!/usr/bin/env python3
"""
Benchmark Stage 3 analysis modules for the FOSS4G paper's Table 2.

Times each pipeline analysis stage end-to-end against the local aggregated
GeoPackage panels (traffic_*_output/*.gpkg) and the cached centrality CSVs.
Skips Stages 1 (collection) and 2 (aggregation) because the raw 15-min
snapshots are not present on this machine.

Run from project root:
    .venv/bin/python benchmark_stage3.py
"""
from __future__ import annotations

import time
import sys
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent

@contextmanager
def timed(label: str, store: list):
    t0 = time.perf_counter()
    yield
    dt = time.perf_counter() - t0
    store.append((label, dt))
    print(f"  {label:<32s} {dt:>7.2f} s")


def main():
    print("=" * 60)
    print("FOSS4G Stage 3 benchmark (analysis modules)")
    print("=" * 60)
    results: list[tuple[str, float]] = []

    # --- geostatistics (Moran's I, LISA, Getis-Ord) ---
    try:
        from trafficpipeline import geostatistics as gs
        with timed("geostatistics (all cities)", results):
            gs.run_analysis(base_dir=str(BASE))
    except Exception as e:
        print(f"  geostatistics: SKIPPED ({type(e).__name__}: {e})")

    # --- LISA Markov + Spatial Markov ---
    try:
        from trafficpipeline import markov
        with timed("markov (all cities)", results):
            markov.run_analysis(base_dir=str(BASE))
    except Exception as e:
        print(f"  markov: SKIPPED ({type(e).__name__}: {e})")

    # --- Multilevel variance decomposition ---
    try:
        from trafficpipeline import multilevel
        with timed("multilevel (all cities)", results):
            multilevel.run_analysis(base_dir=str(BASE))
    except Exception as e:
        print(f"  multilevel: SKIPPED ({type(e).__name__}: {e})")

    # --- H3 robustness ---
    try:
        from trafficpipeline import h3_robustness as h3r
        with timed("h3-robustness (all cities)", results):
            h3r.run_analysis(base_dir=str(BASE))
    except Exception as e:
        print(f"  h3-robustness: SKIPPED ({type(e).__name__}: {e})")

    print("-" * 60)
    if results:
        df = pd.DataFrame(results, columns=["module", "seconds"])
        out = BASE / "analysis_results" / "stage3_benchmark.csv"
        out.parent.mkdir(exist_ok=True)
        df.to_csv(out, index=False)
        print(f"Total Stage 3 wall-clock: {df['seconds'].sum():.1f} s "
              f"({df['seconds'].sum()/60:.1f} min)")
        print(f"Saved: {out}")
    else:
        print("No modules ran successfully.")


if __name__ == "__main__":
    main()
