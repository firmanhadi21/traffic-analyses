#!/usr/bin/env python3
"""
Lebaran Natural Experiment — Jakarta congestion before/during/after Eid al-Fitr.

Tests the demand-synchronization hypothesis using the annual mudik exodus as
a treatment that removes demand while road supply is held constant.

Design (within-segment DiD):
    speed_{s,t} = alpha_s + beta_period[t] + gamma · Lebaran[t]
                                + delta · (Lebaran × Peak)[t] + eps_{s,t}
where
    alpha_s     segment random intercept (absorbs FFS, road class, location)
    beta_period 8 time-period fixed effects (or 24 hours if --hourly)
    gamma       average speed change during the Lebaran window
    delta       extra speed gain at evening peak hours when demand drops
                (THIS is the test: if demand synchronization dominates, delta > 0)

Lebaran 2026 (Eid al-Fitr 1447 AH): approximately 20-21 March 2026 in Indonesia.
Mudik exodus typically starts ~5-7 days before. The script defaults to:
    Lebaran window:  10-23 March 2026
    Baseline window: 1 Jan - 28 Feb 2026 (regular working/school weeks)
Both windows are configurable via --lebaran-start, --lebaran-end,
--baseline-start, --baseline-end.

USAGE (on office desktop with raw data):
    # Adjust --raw-dir to point at the directory of city_traffic_*.gpkg files.
    python lebaran_analysis.py --raw-dir /path/to/jakarta_raw \\
                               --output-dir ./lebaran_results

Outputs:
    lebaran_results/lebaran_did_estimates.csv     coefficient table
    lebaran_results/lebaran_speed_by_week.csv     weekly mean speed by hour
    lebaran_results/lebaran_speed_by_week.png     time-series plot
    lebaran_results/lebaran_pre_post_box.png      pre/during/post box plot
    lebaran_results/lebaran_summary.txt           human-readable summary

REQUIREMENTS:
    pip install geopandas pandas numpy statsmodels matplotlib pyarrow

Notes:
- The script reads only what it needs: segment_id, jam_factor, speed (or
  current_speed), free_flow_speed, plus the timestamp from the filename.
- If your raw GPKGs use different column names, edit COLUMN_ALIASES below.
- Set --sample-rate to 0.1 for a 10% segment sample if memory is tight.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# If the raw GPKG columns are named differently in your data, update here.
COLUMN_ALIASES = {
    "segment_id": ["osm_composite_id", "segment_id", "fid", "id"],
    "speed":      ["current_speed", "speed", "speed_mean"],
    "free_flow":  ["free_flow", "freeflow_speed", "free_flow_speed", "free_flow_mean"],
    "jam_factor": ["jam_factor", "jamFactor", "jam_factor_mean"],
}

# Filename pattern (matches src/trafficpipeline/aggregate.py)
#   Example: jkt_traffic_20260315_073012.gpkg
FILENAME_PATTERN = r"_traffic_(\d{8})_(\d{6})\.gpkg$"

# Default windows (override on CLI)
LEBARAN_START = "2026-03-10"
LEBARAN_END   = "2026-03-23"
BASELINE_START = "2026-01-01"
BASELINE_END   = "2026-02-28"

# Eid al-Fitr 2026 (approximate; actual date depends on moon sighting)
EID_DATE = "2026-03-20"

# Peak hours (Jakarta evening rush)
PEAK_HOURS = list(range(16, 19))  # 16:00, 17:00, 18:00 = evening peak

# Period definitions matching the manuscript Table 3
def hour_to_period(h: int) -> str:
    if 0 <= h < 6:   return "early_morning"
    if 6 <= h < 9:   return "morning_peak"
    if 9 <= h < 12:  return "morning_offpeak"
    if 12 <= h < 14: return "lunch_hours"
    if 14 <= h < 16: return "afternoon_offpeak"
    if 16 <= h < 19: return "evening_peak"
    if 19 <= h < 22: return "evening_offpeak"
    return "late_night"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def parse_timestamp(filepath: str) -> datetime | None:
    import re
    m = re.search(FILENAME_PATTERN, os.path.basename(filepath))
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def resolve_column(gdf: gpd.GeoDataFrame, key: str) -> str | None:
    for alias in COLUMN_ALIASES[key]:
        if alias in gdf.columns:
            return alias
    return None


def load_snapshot(filepath: str, sample_rate: float = 1.0,
                  osm_context: dict | None = None) -> pd.DataFrame | None:
    """Load one raw snapshot and return a tidy DataFrame.

    Parameters
    ----------
    osm_context
        If supplied, expected keys ``wkb_cache`` and ``osm_ref_gdf`` from
        ``trafficpipeline.aggregate``. The snapshot is OSM-matched so the
        returned ``segment_id`` is the stable ``osm_composite_id`` and
        rows without a match are dropped. If ``None``, the loader falls
        back to whichever per-snapshot id column exists (HERE ``id`` etc.),
        which may not be stable across snapshots.
    """
    if osm_context is not None:
        # OSM-stable identifier path. Requires the geometry, so do not
        # set ignore_geometry=True here.
        try:
            gdf = gpd.read_file(filepath)
        except Exception as e:
            print(f"  WARN: failed to read {filepath}: {e}", file=sys.stderr)
            return None
        spd_col = resolve_column(gdf, "speed")
        ff_col  = resolve_column(gdf, "free_flow")
        jam_col = resolve_column(gdf, "jam_factor")
        if spd_col is None:
            print(f"  WARN: no speed column in {filepath} "
                  f"(have {list(gdf.columns)})", file=sys.stderr)
            return None
        try:
            gdf = osm_context["assign"](gdf)
        except Exception as e:
            print(f"  WARN: OSM-match failed for {filepath}: {e}", file=sys.stderr)
            return None
        gdf = gdf.dropna(subset=["osm_composite_id"])
        if len(gdf) == 0:
            return None
        cols = {"osm_composite_id": "segment_id", spd_col: "speed"}
        if ff_col:  cols[ff_col]  = "free_flow"
        if jam_col: cols[jam_col] = "jam_factor"
        df = pd.DataFrame(gdf[list(cols.keys())]).rename(columns=cols)
    else:
        # Fallback: ignore geometry, use whichever id column we find.
        try:
            gdf = gpd.read_file(filepath, ignore_geometry=True)
        except Exception as e:
            print(f"  WARN: failed to read {filepath}: {e}", file=sys.stderr)
            return None
        seg_col = resolve_column(gdf, "segment_id")
        spd_col = resolve_column(gdf, "speed")
        ff_col  = resolve_column(gdf, "free_flow")
        jam_col = resolve_column(gdf, "jam_factor")
        if seg_col is None or spd_col is None:
            print(f"  WARN: missing required columns in {filepath} "
                  f"(have {list(gdf.columns)})", file=sys.stderr)
            return None
        cols = {seg_col: "segment_id", spd_col: "speed"}
        if ff_col:  cols[ff_col]  = "free_flow"
        if jam_col: cols[jam_col] = "jam_factor"
        df = gdf[list(cols.keys())].rename(columns=cols)

    ts = parse_timestamp(filepath)
    if ts is None:
        return None
    df["timestamp"] = ts

    if sample_rate < 1.0:
        df = df.sample(frac=sample_rate, random_state=42)

    return df


def in_window(ts: datetime, start: str, end: str) -> bool:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
    return s <= ts < e


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def build_osm_context(city: str, base_dir: Path) -> dict | None:
    """Load the OSM mapping + WKB cache so that load_snapshot can assign
    a stable ``osm_composite_id`` to every segment in a raw snapshot."""
    try:
        from trafficpipeline.aggregate import (
            _load_osm_mapping, _build_wkb_cache, _assign_osm_ids,
        )
    except ImportError as e:
        print(f"  NOTE: trafficpipeline.aggregate not importable ({e}); "
              "falling back to non-OSM segment identifier.", file=sys.stderr)
        return None
    try:
        osm_ref_gdf, wkt_hash_mapping, create_geom_hash = _load_osm_mapping(
            city, base_dir,
        )
    except FileNotFoundError as e:
        print(f"  NOTE: OSM reference for city '{city}' not found ({e}); "
              "falling back to non-OSM segment identifier.", file=sys.stderr)
        return None

    # WKB cache wants a first raw snapshot to seed; we will rebuild it
    # lazily on the first snapshot we read.
    return {
        "osm_ref_gdf": osm_ref_gdf,
        "wkt_hash_mapping": wkt_hash_mapping,
        "create_geom_hash": create_geom_hash,
        "wkb_cache": {},
        "assign": lambda gdf: _assign_osm_ids(
            gdf, _seeded_cache(gdf, osm_ref_gdf, wkt_hash_mapping,
                               create_geom_hash, _CACHE_HOLDER),
            osm_ref_gdf,
        ),
    }


_CACHE_HOLDER: dict = {"cache": None}


def _seeded_cache(gdf, osm_ref_gdf, wkt_hash_mapping, create_geom_hash, holder):
    """Build the WKB cache once (on the first snapshot) and reuse it
    for every subsequent snapshot. Mirrors aggregate_city behaviour."""
    if holder["cache"] is None:
        from trafficpipeline.aggregate import _build_wkb_cache
        holder["cache"] = _build_wkb_cache(
            gdf, osm_ref_gdf, wkt_hash_mapping, create_geom_hash,
        )
        print(f"  WKB→OSM cache built: {len(holder['cache']):,} entries",
              file=sys.stderr)
    return holder["cache"]


def collect_panel(raw_dir: Path, lebaran_start: str, lebaran_end: str,
                  baseline_start: str, baseline_end: str,
                  sample_rate: float,
                  osm_context: dict | None = None) -> pd.DataFrame:
    """Walk raw_dir, load snapshots inside the windows, return a long panel."""
    pattern = str(raw_dir / "*.gpkg")
    files = sorted(glob.glob(pattern))
    print(f"Found {len(files):,} files matching {pattern}")
    if not files:
        raise FileNotFoundError(f"No .gpkg files in {raw_dir}")

    keep = []
    for fp in files:
        ts = parse_timestamp(fp)
        if ts is None:
            continue
        if in_window(ts, lebaran_start, lebaran_end) or \
           in_window(ts, baseline_start, baseline_end):
            keep.append(fp)

    print(f"  {len(keep):,} files fall in the Lebaran or baseline windows")
    if not keep:
        raise ValueError("No files in selected windows. Check --lebaran-start "
                         "and --baseline-start match your data range.")

    frames = []
    for i, fp in enumerate(keep):
        if (i + 1) % 200 == 0:
            print(f"  Loaded {i+1}/{len(keep)} snapshots")
        df = load_snapshot(fp, sample_rate=sample_rate, osm_context=osm_context)
        if df is not None and len(df):
            frames.append(df)

    if not frames:
        raise RuntimeError("No snapshots produced any rows. If you see "
                           "WKB→OSM cache messages but zero matches, the OSM "
                           "reference may be stale; rerun "
                           "`traffic-pipeline aggregate --city jkt` to refresh "
                           "the cache.")
    panel = pd.concat(frames, ignore_index=True)
    print(f"  Total observations: {len(panel):,} "
          f"({panel['segment_id'].nunique():,} segments)")
    return panel


def annotate(panel: pd.DataFrame, lebaran_start: str, lebaran_end: str) -> pd.DataFrame:
    """Add lebaran / period / peak / hour columns."""
    panel = panel.copy()
    panel["hour"] = panel["timestamp"].dt.hour
    panel["date"] = panel["timestamp"].dt.date
    panel["weekday"] = panel["timestamp"].dt.dayofweek  # 0=Mon, 6=Sun
    panel["period"] = panel["hour"].apply(hour_to_period)
    panel["peak"] = panel["hour"].isin(PEAK_HOURS).astype(int)

    s = datetime.strptime(lebaran_start, "%Y-%m-%d").date()
    e = datetime.strptime(lebaran_end, "%Y-%m-%d").date()
    panel["lebaran"] = panel["date"].between(s, e).astype(int)

    return panel


def fit_did(panel: pd.DataFrame) -> dict:
    """Fit the within-segment DiD model and return coefficients."""
    import statsmodels.formula.api as smf

    # Drop missing speed
    df = panel.dropna(subset=["speed"]).copy()
    # Speed sanity (HERE returns m/s in some endpoints; convert to km/h if needed)
    if df["speed"].max() < 50 and df["speed"].median() < 15:
        print("  NOTE: speed appears to be in m/s, converting to km/h")
        df["speed"] = df["speed"] * 3.6

    print(f"  Fitting DiD on {len(df):,} obs / {df['segment_id'].nunique():,} segments...")

    # Model 1: main + interaction with peak
    model = smf.mixedlm(
        "speed ~ C(period) + lebaran + lebaran:peak",
        data=df, groups=df["segment_id"],
    ).fit(reml=True)

    fe = model.fe_params
    pv = model.pvalues
    out = {
        "n_obs": len(df),
        "n_segments": int(df["segment_id"].nunique()),
        "beta_lebaran": float(fe.get("lebaran", np.nan)),
        "p_lebaran":    float(pv.get("lebaran", np.nan)),
        "beta_lebaran_peak": float(fe.get("lebaran:peak", np.nan)),
        "p_lebaran_peak":    float(pv.get("lebaran:peak", np.nan)),
        "var_segment": float(model.cov_re.iloc[0, 0]),
        "var_resid":   float(model.scale),
    }
    print(f"  beta_lebaran       = {out['beta_lebaran']:+.3f} km/h "
          f"(p={out['p_lebaran']:.2e})")
    print(f"  beta_lebaran×peak  = {out['beta_lebaran_peak']:+.3f} km/h "
          f"(p={out['p_lebaran_peak']:.2e})")

    # Pre/During/Post split for descriptive comparison
    return out, model


def descriptive_tables(panel: pd.DataFrame, lebaran_start: str, lebaran_end: str,
                       out_dir: Path) -> pd.DataFrame:
    """Weekly mean speed by hour-of-day, around Lebaran."""
    df = panel.dropna(subset=["speed"]).copy()
    df["iso_week"] = df["timestamp"].dt.isocalendar().week
    df["iso_year"] = df["timestamp"].dt.isocalendar().year
    df["week_key"] = df["iso_year"].astype(str) + "W" + df["iso_week"].astype(str).str.zfill(2)

    weekly = (df.groupby(["week_key", "hour"])["speed"]
                .agg(["mean", "median", "count"]).reset_index())
    weekly.to_csv(out_dir / "lebaran_speed_by_week.csv", index=False)
    return weekly


def plot_speed_by_week(weekly: pd.DataFrame, lebaran_start: str, lebaran_end: str,
                       out_dir: Path):
    """Heatmap-style plot of hour × week mean speed."""
    pivot = weekly.pivot(index="hour", columns="week_key", values="mean")
    # Order columns chronologically
    pivot = pivot.reindex(columns=sorted(pivot.columns))

    fig, ax = plt.subplots(figsize=(14, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn",
                   vmin=10, vmax=40, origin="lower")
    ax.set_yticks(range(0, 24))
    ax.set_yticklabels([f"{h:02d}:00" for h in range(0, 24)])
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("ISO week")
    ax.set_ylabel("Hour of day")
    ax.set_title("Jakarta mean speed by hour-of-day across weeks\n"
                 "(green = faster, red = slower; Lebaran weeks expected to brighten)")

    # Highlight Lebaran columns
    s = datetime.strptime(lebaran_start, "%Y-%m-%d")
    e = datetime.strptime(lebaran_end, "%Y-%m-%d")
    for i, wk in enumerate(pivot.columns):
        yr = int(wk[:4]); w = int(wk[5:])
        # Approximate the Monday of ISO week
        wk_start = datetime.fromisocalendar(yr, w, 1)
        wk_end   = wk_start + timedelta(days=6)
        if not (wk_end < s or wk_start > e):
            ax.axvline(i, color="black", lw=1.2, alpha=0.8)

    plt.colorbar(im, ax=ax, label="Mean speed (km/h)")
    plt.tight_layout()
    plt.savefig(out_dir / "lebaran_speed_by_week.png", dpi=150, bbox_inches="tight")
    plt.close()


def plot_pre_post_box(panel: pd.DataFrame, lebaran_start: str, lebaran_end: str,
                      out_dir: Path):
    """Box plot of evening-peak speed: baseline vs lebaran."""
    df = panel.dropna(subset=["speed"]).copy()
    peak = df[df["peak"] == 1]
    peak["group"] = peak["lebaran"].map({0: "Baseline", 1: "Lebaran window"})

    fig, ax = plt.subplots(figsize=(8, 6))
    data = [peak[peak["lebaran"] == 0]["speed"].sample(min(50000, (peak["lebaran"]==0).sum()), random_state=0),
            peak[peak["lebaran"] == 1]["speed"].sample(min(50000, (peak["lebaran"]==1).sum()), random_state=0)]
    ax.boxplot(data, labels=["Baseline\n(Jan-Feb 2026)", "Lebaran window\n(10-23 Mar 2026)"],
               showfliers=False)
    ax.set_ylabel("Evening-peak speed (km/h)")
    ax.set_title("Jakarta evening-peak speed: baseline vs Lebaran\n"
                 "(if demand-sync dominates, Lebaran box should sit higher)")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "lebaran_pre_post_box.png", dpi=150, bbox_inches="tight")
    plt.close()


def write_summary(estimates: dict, out_dir: Path, args):
    txt = f"""LEBARAN NATURAL EXPERIMENT — JAKARTA
====================================

Data window
  Baseline:  {args.baseline_start} to {args.baseline_end}
  Lebaran :  {args.lebaran_start} to {args.lebaran_end}
  Eid date :  {args.eid_date}

Sample
  Observations: {estimates['n_obs']:,}
  Segments    : {estimates['n_segments']:,}

DiD estimates (within-segment, time-period fixed effects)
  beta_lebaran      = {estimates['beta_lebaran']:+.3f} km/h   (p = {estimates['p_lebaran']:.3g})
    Interpretation : Average speed change in the Lebaran window across ALL hours.
    Sign expected  : POSITIVE if demand removal raises speeds.

  beta_lebaran×peak = {estimates['beta_lebaran_peak']:+.3f} km/h   (p = {estimates['p_lebaran_peak']:.3g})
    Interpretation : EXTRA speed gain during evening peak (16:00-18:59) on top
                     of the average Lebaran effect.
    Sign expected  : POSITIVE and LARGE if demand synchronization dominates
                     — peak hours benefit most when synchronized demand is gone.

Variance components
  Between-segment variance : {estimates['var_segment']:.2f}
  Within-segment residual  : {estimates['var_resid']:.2f}
  ICC                      : {estimates['var_segment'] / (estimates['var_segment'] + estimates['var_resid']):.1%}

Interpretation for the TRIP manuscript R1.3 response
  - If beta_lebaran>0 AND beta_lebaran×peak>0 (both significant), this is direct
    causal evidence that demand-driven peaks generate the observed congestion.
  - The size of beta_lebaran×peak (in km/h) is the headline number: if peak-hour
    speed gains under Lebaran are >> off-peak speed gains, demand synchronization
    is the operative mechanism.
  - Caveats: N=1 event, partial demand removal (not everyone leaves Jakarta),
    intercity highways may behave differently (toll arteries during mudik).

Outputs:
  lebaran_did_estimates.csv      one-row coefficient table
  lebaran_speed_by_week.csv      weekly hour-of-day mean speed
  lebaran_speed_by_week.png      hour × week heatmap
  lebaran_pre_post_box.png       baseline vs lebaran peak-speed box plot
"""
    (out_dir / "lebaran_summary.txt").write_text(txt)
    print("\n" + txt)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", required=True, type=Path,
                   help="Directory of raw city_traffic_YYYYMMDD_HHMMSS.gpkg snapshots")
    p.add_argument("--output-dir", default="lebaran_results", type=Path)
    p.add_argument("--city", default="jkt",
                   help="City code for OSM-stable segment matching "
                        "(jkt/bdg/smg). Set to 'none' to skip OSM matching "
                        "and fall back to the snapshot's native id column.")
    p.add_argument("--base-dir", default=".", type=Path,
                   help="Project root containing osm_reference/ (default '.').")
    p.add_argument("--lebaran-start", default=LEBARAN_START)
    p.add_argument("--lebaran-end",   default=LEBARAN_END)
    p.add_argument("--baseline-start", default=BASELINE_START)
    p.add_argument("--baseline-end",   default=BASELINE_END)
    p.add_argument("--eid-date", default=EID_DATE)
    p.add_argument("--sample-rate", type=float, default=1.0,
                   help="Random sample fraction per snapshot (default 1.0)")
    args = p.parse_args()

    args.output_dir.mkdir(exist_ok=True, parents=True)

    print("=" * 70)
    print(f"LEBARAN NATURAL EXPERIMENT  ({args.lebaran_start} ↔ {args.baseline_start})")
    print("=" * 70)

    if args.city.lower() == "none":
        osm_context = None
        print("  OSM matching: DISABLED (using raw snapshot id column)")
    else:
        print(f"  Loading OSM context for city '{args.city}' …")
        osm_context = build_osm_context(args.city, args.base_dir)

    panel = collect_panel(
        args.raw_dir, args.lebaran_start, args.lebaran_end,
        args.baseline_start, args.baseline_end, args.sample_rate,
        osm_context=osm_context,
    )
    panel = annotate(panel, args.lebaran_start, args.lebaran_end)

    print("\nDescriptive: weekly mean speed by hour-of-day...")
    weekly = descriptive_tables(panel, args.lebaran_start, args.lebaran_end, args.output_dir)
    plot_speed_by_week(weekly, args.lebaran_start, args.lebaran_end, args.output_dir)
    plot_pre_post_box(panel, args.lebaran_start, args.lebaran_end, args.output_dir)

    print("\nFitting DiD mixed model...")
    estimates, model = fit_did(panel)

    pd.DataFrame([estimates]).to_csv(args.output_dir / "lebaran_did_estimates.csv", index=False)
    (args.output_dir / "lebaran_did_model_summary.txt").write_text(str(model.summary()))

    write_summary(estimates, args.output_dir, args)
    print(f"\nAll outputs written to {args.output_dir.absolute()}")


if __name__ == "__main__":
    main()
