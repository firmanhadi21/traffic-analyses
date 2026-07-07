"""Positive-control analysis: free-flow speed as a spatial predictor of current speed.

Computes the Pearson R^2 between free-flow speed and current speed per city, at
two aggregation levels:

  * segment-level  -- segment means collapsed across the 8 temporal periods
                      (the "between-segment" statistic reported in the manuscript)
  * pooled panel   -- all segment x period observations

Rationale: free-flow speed is a road-design characteristic (lane count, speed
limit, road class) and should be strongly predictable from segment identity.
Recovering this known spatial signal shows the pipeline can detect spatial
structure where it exists, so the null centrality--congestion result is not a
methodological artifact.

Outputs: analysis_results/positive_control_r2.csv
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from scipy import stats

BASE = Path(__file__).parent
OUT = BASE / "analysis_results" / "positive_control_r2.csv"

CITIES = {
    "bdg": "traffic_bdg_output",
    "jkt": "traffic_jkt_output",
    "smg": "traffic_smg_output",
}


def load_panel(city_code: str) -> pd.DataFrame:
    """Long panel (segment x period) of speed and free-flow speed."""
    folder = BASE / CITIES[city_code]
    frames = []
    for fp in sorted(folder.glob(f"*_{city_code}.gpkg")):
        gdf = gpd.read_file(fp)
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


def main() -> None:
    rows = []
    for code in CITIES:
        panel = load_panel(code)
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
        print(
            f"{code}: segments={len(seg):,}  "
            f"segment-level R2={r_seg**2:.3f}  pooled R2={r_pool**2:.3f}"
        )

    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
