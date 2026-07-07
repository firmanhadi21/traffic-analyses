"""Positive-control analysis: free-flow speed as a spatial predictor of current speed.

Free-flow speed is a road-design characteristic (lane count, speed limit, road
class) and should be strongly predictable from segment identity. Recovering this
known spatial signal demonstrates that the pipeline can detect spatial structure
where it exists, so a null centrality--congestion result cannot be attributed to
insufficient power, spatial-matching errors, or data-quality problems.

Computes the Pearson R^2 between free-flow speed and current speed per city at
two aggregation levels:

* ``segment-level`` -- segment means collapsed across the temporal periods
  (the between-segment statistic reported in the manuscript)
* ``pooled panel`` -- all segment x period observations

Outputs ``positive_control_r2.csv`` in the analysis-results directory.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from scipy import stats

from trafficpipeline.config import CITIES, TIME_PERIODS


def load_panel(city_code: str, base_dir: str | Path = ".") -> pd.DataFrame:
    """Build a long panel (segment x period) of current speed and free-flow speed."""
    folder = Path(base_dir) / CITIES[city_code]["traffic_output_dir"]
    frames = []
    for period in TIME_PERIODS:
        fp = folder / f"{period}_{city_code}.gpkg"
        if not fp.exists():
            continue
        gdf = gpd.read_file(str(fp))
        if "speed_mean" not in gdf.columns or "free_flow_mean" not in gdf.columns:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "segment_id": gdf["osm_composite_id"],
                    "speed": gdf["speed_mean"],
                    "ffs": gdf["free_flow_mean"],
                }
            )
        )
    if not frames:
        raise FileNotFoundError(f"No period GPKGs with speed columns for {city_code}")
    return pd.concat(frames, ignore_index=True).dropna(subset=["speed", "ffs"])


def compute_positive_control(base_dir: str | Path = ".") -> pd.DataFrame:
    """Per-city Pearson R^2 of free-flow speed vs current speed, both levels."""
    rows = []
    for code in CITIES:
        panel = load_panel(code, base_dir)
        seg = panel.groupby("segment_id")[["speed", "ffs"]].mean()

        r_seg, p_seg = stats.pearsonr(seg["ffs"], seg["speed"])
        r_pool, p_pool = stats.pearsonr(panel["ffs"], panel["speed"])

        rows.append(
            {
                "city": code,
                "n_segments": len(seg),
                "n_panel_obs": len(panel),
                "r2_segment_level": round(r_seg**2, 4),
                "p_segment_level": p_seg,
                "r2_pooled_panel": round(r_pool**2, 4),
                "p_pooled_panel": p_pool,
            }
        )
    return pd.DataFrame(rows)


def run_analysis(
    base_dir: str | Path = ".",
    output_dir: str | Path = "analysis_results",
) -> pd.DataFrame:
    """Run the positive-control analysis and write ``positive_control_r2.csv``."""
    df = compute_positive_control(base_dir)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "positive_control_r2.csv"
    df.to_csv(csv_path, index=False)

    for row in df.itertuples(index=False):
        print(
            f"{row.city}: segments={row.n_segments:,}  "
            f"segment-level R2={row.r2_segment_level:.3f}  "
            f"pooled R2={row.r2_pooled_panel:.3f}"
        )
    print(f"written: {csv_path}")
    return df
