#!/usr/bin/env python3
"""
Lebaran Natural Experiment — Jakarta congestion before/during Eid al-Fitr.

Tests the demand-synchronization hypothesis using the annual mudik exodus as
a treatment that removes demand while the road network is held physically
constant. Uses both Lebaran 2025 and Lebaran 2026 as treatments, with a
year fixed effect to net out structural change between the two years.

Design (two-window within-segment DiD):
    speed_{s,d,h} = α_s + γ_year + β_period[h]
                  + δ · Lebaran[d] + θ · (Lebaran × Peak)[d,h] + ε
where
    α_s         segment random intercept (absorbs FFS, road class, location)
    γ_year      year fixed effect (2025 vs 2026; absorbs network changes)
    β_period    8 time-period fixed effects
    δ           average speed change in the Lebaran windows
    θ           extra speed gain at evening peak when synchronized demand
                is removed (THIS is the headline test for the demand-
                synchronization mechanism)

Default windows (override on CLI):
    2025: baseline 2025-03-01 → 2025-03-23,  Lebaran 2025-03-24 → 2025-04-06
    2026: baseline 2026-01-01 → 2026-03-13,  Lebaran 2026-03-14 → 2026-03-23
Eid al-Fitr is approximately:
    2025: 30–31 March    1446 AH
    2026: 20–21 March    1447 AH

USAGE (on office desktop with raw data):
    python lebaran_analysis.py --raw-dir traffic_data_jkt \\
                               --city jkt \\
                               --output-dir lebaran_results

Outputs:
    lebaran_did_estimates.csv   one-row coefficient table
    lebaran_speed_by_week.csv   weekly hour-of-day mean speed
    lebaran_speed_by_week.png   hour × week heatmap
    lebaran_pre_post_box.png    box plot of evening-peak speed by year × window
    lebaran_summary.txt         human-readable summary

REQUIREMENTS:
    pip install geopandas pandas numpy statsmodels matplotlib pyarrow

Notes:
- The script reads only what it needs: segment_id, jam_factor, speed (or
  current_speed), free_flow_speed, plus the timestamp from the filename.
- If your raw GPKGs use different column names, edit COLUMN_ALIASES below.
- Set --sample-rate to 0.1 for a 10% segment sample if memory is tight.
- Pass --city none to bypass OSM matching and use the snapshot's native id
  column (faster, but only safe if the id is stable across snapshots).
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

# Default windows (override on CLI).
# Two-window DiD: pool both years; Lebaran is the "treatment" in each.
# Eid al-Fitr dates (subject to moon-sighting confirmation):
#   2025: approximately Sunday 30 March – Monday 31 March
#   2026: approximately Friday 20 March – Saturday 21 March
# Mudik exodus typically starts ~5–7 days before Eid and return ~5 days after.

# 2025 windows
LEBARAN_2025_START   = "2025-03-24"
LEBARAN_2025_END     = "2025-04-06"
BASELINE_2025_START  = "2025-03-01"   # earliest plausible start of collection
BASELINE_2025_END    = "2025-03-23"

# 2026 windows
LEBARAN_2026_START   = "2026-03-14"
LEBARAN_2026_END     = "2026-03-23"   # data cutoff
BASELINE_2026_START  = "2026-01-01"
BASELINE_2026_END    = "2026-03-13"

EID_2025 = "2025-03-30"
EID_2026 = "2026-03-21"

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


def classify_window(ts: datetime, windows: dict) -> tuple[int | None, int]:
    """Return (year_int, lebaran_int) if ts falls inside one of the four
    named windows in ``windows``; ``year`` is None if not in any window.

    ``windows`` keys: 'b2025', 'l2025', 'b2026', 'l2026'.
    """
    if in_window(ts, *windows["b2025"]): return (2025, 0)
    if in_window(ts, *windows["l2025"]): return (2025, 1)
    if in_window(ts, *windows["b2026"]): return (2026, 0)
    if in_window(ts, *windows["l2026"]): return (2026, 1)
    return (None, 0)


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


def collect_panel(raw_dir: Path, windows: dict, sample_rate: float,
                  osm_context: dict | None = None) -> pd.DataFrame:
    """Walk raw_dir, load snapshots that fall inside any of the four
    named windows, return a long panel with year + lebaran columns set."""
    pattern = str(raw_dir / "*.gpkg")
    files = sorted(glob.glob(pattern))
    print(f"Found {len(files):,} files matching {pattern}")
    if not files:
        raise FileNotFoundError(f"No .gpkg files in {raw_dir}")

    keep: list[tuple[str, int, int]] = []
    for fp in files:
        ts = parse_timestamp(fp)
        if ts is None:
            continue
        year, leb = classify_window(ts, windows)
        if year is not None:
            keep.append((fp, year, leb))

    # Per-window counts for the user.
    counts = {
        "b2025": sum(1 for _, y, l in keep if y == 2025 and l == 0),
        "l2025": sum(1 for _, y, l in keep if y == 2025 and l == 1),
        "b2026": sum(1 for _, y, l in keep if y == 2026 and l == 0),
        "l2026": sum(1 for _, y, l in keep if y == 2026 and l == 1),
    }
    print(f"  Snapshots per window: "
          f"b2025={counts['b2025']:,}, l2025={counts['l2025']:,}, "
          f"b2026={counts['b2026']:,}, l2026={counts['l2026']:,}")
    if not keep:
        raise ValueError(
            "No files in any of the four windows. Check the dates against "
            "your data range (earliest and latest snapshots)."
        )
    # Warn loudly if a window is empty — DiD needs all four for the FE to be
    # identified.
    empty = [k for k, v in counts.items() if v == 0]
    if empty:
        print(f"  WARNING: window(s) {empty} have zero snapshots. The "
              "year-FE DiD may be under-identified. Adjust the window dates "
              "via CLI flags.", file=sys.stderr)

    frames = []
    for i, (fp, year, leb) in enumerate(keep):
        if (i + 1) % 200 == 0:
            print(f"  Loaded {i+1}/{len(keep)} snapshots")
        df = load_snapshot(fp, sample_rate=sample_rate, osm_context=osm_context)
        if df is None or len(df) == 0:
            continue
        df["year"] = year
        df["lebaran"] = leb
        frames.append(df)

    if not frames:
        raise RuntimeError("No snapshots produced any rows. If you see "
                           "WKB→OSM cache messages but zero matches, the OSM "
                           "reference may be stale; rerun "
                           "`traffic-pipeline aggregate --city jkt` to refresh "
                           "the cache.")
    panel = pd.concat(frames, ignore_index=True)
    print(f"  Total observations: {len(panel):,} "
          f"({panel['segment_id'].nunique():,} segments across both years)")
    return panel


def annotate(panel: pd.DataFrame) -> pd.DataFrame:
    """Add period / peak / hour / date / weekday columns.

    ``year`` and ``lebaran`` are populated upstream in ``collect_panel`` from
    the window definitions.
    """
    panel = panel.copy()
    panel["hour"] = panel["timestamp"].dt.hour
    panel["date"] = panel["timestamp"].dt.date
    panel["weekday"] = panel["timestamp"].dt.dayofweek  # 0=Mon, 6=Sun
    panel["period"] = panel["hour"].apply(hour_to_period)
    panel["peak"] = panel["hour"].isin(PEAK_HOURS).astype(int)
    return panel


def fit_did(panel: pd.DataFrame) -> tuple[dict, object]:
    """Fit the two-window within-segment DiD model with a year fixed effect.

    Specification (random intercept on segment_id):
        speed ~ C(period) + C(year) + lebaran + lebaran:peak

    Returns (estimates_dict, fitted_model).
    """
    import statsmodels.formula.api as smf

    df = panel.dropna(subset=["speed"]).copy()
    # HERE Traffic v7 returns m/s on some endpoints; convert to km/h heuristically.
    if df["speed"].max() < 50 and df["speed"].median() < 15:
        print("  NOTE: speed appears to be in m/s, converting to km/h")
        df["speed"] = df["speed"] * 3.6

    # Ensure year is treated categorically (2025 vs 2026 dummy).
    df["year"] = df["year"].astype(int)

    print(f"  Fitting two-window DiD on {len(df):,} obs / "
          f"{df['segment_id'].nunique():,} segments...")
    by_year = df.groupby("year").size()
    print(f"  Records by year: " +
          ", ".join(f"{y}={n:,}" for y, n in by_year.items()))

    formula = "speed ~ C(period) + C(year) + lebaran + lebaran:peak"
    model = smf.mixedlm(formula, data=df, groups=df["segment_id"]).fit(reml=True)

    fe = model.fe_params
    pv = model.pvalues

    # Identify the year-FE parameter name (statsmodels labels it like
    # 'C(year)[T.2026]' for the non-reference year).
    year_key = next(
        (k for k in fe.index if k.startswith("C(year)[T.")),
        None,
    )

    out = {
        "n_obs":               len(df),
        "n_segments":          int(df["segment_id"].nunique()),
        "n_obs_2025":          int(by_year.get(2025, 0)),
        "n_obs_2026":          int(by_year.get(2026, 0)),
        "beta_lebaran":        float(fe.get("lebaran", np.nan)),
        "p_lebaran":           float(pv.get("lebaran", np.nan)),
        "beta_lebaran_peak":   float(fe.get("lebaran:peak", np.nan)),
        "p_lebaran_peak":      float(pv.get("lebaran:peak", np.nan)),
        "beta_year":           float(fe[year_key]) if year_key else np.nan,
        "p_year":              float(pv[year_key]) if year_key else np.nan,
        "year_key":            year_key or "",
        "var_segment":         float(model.cov_re.iloc[0, 0]),
        "var_resid":           float(model.scale),
        "formula":             formula,
    }
    print(f"  beta_lebaran       = {out['beta_lebaran']:+.3f} km/h "
          f"(p={out['p_lebaran']:.2e})")
    print(f"  beta_lebaran×peak  = {out['beta_lebaran_peak']:+.3f} km/h "
          f"(p={out['p_lebaran_peak']:.2e})")
    if year_key:
        print(f"  beta_year ({year_key}) = {out['beta_year']:+.3f} km/h "
              f"(p={out['p_year']:.2e})")
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


def plot_pre_post_box(panel: pd.DataFrame, out_dir: Path):
    """Box plot of evening-peak speed: four groups (baseline × Lebaran × year)."""
    df = panel.dropna(subset=["speed"]).copy()
    peak = df[df["peak"] == 1].copy()
    peak["group"] = (
        peak["year"].astype(str)
        + " " + peak["lebaran"].map({0: "baseline", 1: "Lebaran"})
    )

    order = ["2025 baseline", "2025 Lebaran", "2026 baseline", "2026 Lebaran"]
    data = []
    for g in order:
        s = peak[peak["group"] == g]["speed"]
        if len(s) == 0:
            data.append(np.array([]))
        else:
            data.append(s.sample(min(50000, len(s)), random_state=0).values)

    fig, ax = plt.subplots(figsize=(9, 6))
    bp = ax.boxplot(data, labels=order, showfliers=False, patch_artist=True)
    palette = ["#cccccc", "#e74c3c", "#cccccc", "#e74c3c"]
    for patch, c in zip(bp["boxes"], palette):
        patch.set_facecolor(c); patch.set_alpha(0.65)
    ax.set_ylabel("Evening-peak speed (km/h)")
    ax.set_title("Jakarta evening-peak speed by year × Lebaran window\n"
                 "(if demand-sync dominates, the red Lebaran boxes sit "
                 "higher than the grey baseline boxes in each year)")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "lebaran_pre_post_box.png", dpi=150, bbox_inches="tight")
    plt.close()


def write_summary(estimates: dict, out_dir: Path, args):
    txt = f"""LEBARAN NATURAL EXPERIMENT — JAKARTA
====================================

Design
  Two-window difference-in-differences (Lebaran 2025 + Lebaran 2026)
  with within-segment random intercepts and a year fixed effect.
  Formula: {estimates['formula']}

Windows
  Baseline 2025: {args.baseline_2025_start} → {args.baseline_2025_end}
  Lebaran  2025: {args.lebaran_2025_start} → {args.lebaran_2025_end}   (Eid {args.eid_2025})
  Baseline 2026: {args.baseline_2026_start} → {args.baseline_2026_end}
  Lebaran  2026: {args.lebaran_2026_start} → {args.lebaran_2026_end}   (Eid {args.eid_2026})

Sample
  Observations    : {estimates['n_obs']:,}
  Segments        : {estimates['n_segments']:,}
  Obs in 2025     : {estimates['n_obs_2025']:,}
  Obs in 2026     : {estimates['n_obs_2026']:,}

DiD estimates (within-segment, time-period fixed effects, year FE)
  beta_lebaran      = {estimates['beta_lebaran']:+.3f} km/h   (p = {estimates['p_lebaran']:.3g})
    Interpretation : Average speed change in the Lebaran windows across ALL hours,
                     after netting out the year fixed effect and time-of-day.
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

Year fixed effect
  beta_{estimates['year_key']:<24} = {estimates['beta_year']:+.3f} km/h   (p = {estimates['p_year']:.3g})
    Interpretation : Average speed change in 2026 vs 2025 (positive = faster,
                     negative = slower). Captures structural changes (network
                     growth, new transit) and any drift between the two years.

Interpretation for the TRIP manuscript R1.3 response
  - If beta_lebaran>0 AND beta_lebaran×peak>0 (both significant), this is direct
    causal evidence that demand-driven peaks generate the observed congestion.
  - The size of beta_lebaran×peak (in km/h) is the headline number: if peak-hour
    speed gains under Lebaran are >> off-peak speed gains, demand synchronization
    is the operative mechanism.
  - The two-Lebaran design adds replication: the effect is estimated across two
    independent annual events, with the year FE controlling for any structural
    change in network capacity or demand level between 2025 and 2026.
  - Caveats: partial demand removal (not everyone leaves Jakarta); intercity
    toll arteries may behave differently from urban roads during mudik.

Outputs:
  lebaran_did_estimates.csv      one-row coefficient table
  lebaran_speed_by_week.csv      weekly hour-of-day mean speed
  lebaran_speed_by_week.png      hour × week heatmap
  lebaran_pre_post_box.png       year × Lebaran peak-speed box plot
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
    # 2025 windows
    p.add_argument("--lebaran-2025-start",  default=LEBARAN_2025_START)
    p.add_argument("--lebaran-2025-end",    default=LEBARAN_2025_END)
    p.add_argument("--baseline-2025-start", default=BASELINE_2025_START)
    p.add_argument("--baseline-2025-end",   default=BASELINE_2025_END)
    p.add_argument("--eid-2025",            default=EID_2025)
    # 2026 windows
    p.add_argument("--lebaran-2026-start",  default=LEBARAN_2026_START)
    p.add_argument("--lebaran-2026-end",    default=LEBARAN_2026_END)
    p.add_argument("--baseline-2026-start", default=BASELINE_2026_START)
    p.add_argument("--baseline-2026-end",   default=BASELINE_2026_END)
    p.add_argument("--eid-2026",            default=EID_2026)
    p.add_argument("--sample-rate", type=float, default=1.0,
                   help="Random sample fraction per snapshot (default 1.0)")
    args = p.parse_args()

    args.output_dir.mkdir(exist_ok=True, parents=True)

    print("=" * 70)
    print("LEBARAN NATURAL EXPERIMENT — two-window DiD (2025 + 2026)")
    print(f"  2025: baseline {args.baseline_2025_start}→{args.baseline_2025_end}"
          f", Lebaran {args.lebaran_2025_start}→{args.lebaran_2025_end}"
          f"  (Eid {args.eid_2025})")
    print(f"  2026: baseline {args.baseline_2026_start}→{args.baseline_2026_end}"
          f", Lebaran {args.lebaran_2026_start}→{args.lebaran_2026_end}"
          f"  (Eid {args.eid_2026})")
    print("=" * 70)

    windows = {
        "b2025": (args.baseline_2025_start, args.baseline_2025_end),
        "l2025": (args.lebaran_2025_start,  args.lebaran_2025_end),
        "b2026": (args.baseline_2026_start, args.baseline_2026_end),
        "l2026": (args.lebaran_2026_start,  args.lebaran_2026_end),
    }

    if args.city.lower() == "none":
        osm_context = None
        print("  OSM matching: DISABLED (using raw snapshot id column)")
    else:
        print(f"  Loading OSM context for city '{args.city}' …")
        osm_context = build_osm_context(args.city, args.base_dir)

    panel = collect_panel(
        args.raw_dir, windows, args.sample_rate, osm_context=osm_context,
    )
    panel = annotate(panel)

    print("\nDescriptive: weekly mean speed by hour-of-day...")
    # Use the 2026 window for the heatmap highlight (more recent + cutoff-anchored).
    weekly = descriptive_tables(
        panel, args.lebaran_2026_start, args.lebaran_2026_end, args.output_dir,
    )
    plot_speed_by_week(
        weekly, args.lebaran_2026_start, args.lebaran_2026_end, args.output_dir,
    )
    plot_pre_post_box(panel, args.output_dir)

    print("\nFitting DiD mixed model...")
    estimates, model = fit_did(panel)

    pd.DataFrame([estimates]).to_csv(args.output_dir / "lebaran_did_estimates.csv", index=False)
    (args.output_dir / "lebaran_did_model_summary.txt").write_text(str(model.summary()))

    write_summary(estimates, args.output_dir, args)
    print(f"\nAll outputs written to {args.output_dir.absolute()}")


if __name__ == "__main__":
    main()
