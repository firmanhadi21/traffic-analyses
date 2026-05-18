#!/usr/bin/env python3
"""
Supplementary Figure S5: Jakarta congestion hotspots with MRT/TransJakarta overlay.

Loads jkt_evening_peak_lisa.gpkg, extracts MRT stations + TransJakarta stops
from OpenStreetMap, and produces a single annotated map. Addresses R3.4.
"""

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import pandas as pd

BASE = Path(__file__).resolve().parent
LISA = BASE / "lisa_results" / "jkt_evening_peak_lisa.gpkg"
FIG = BASE / "figures" / "jkt_hotspots_transit_overlay.png"
FIG.parent.mkdir(exist_ok=True)

# Jakarta bbox (matches manuscript)
BBOX = (-6.4096, 106.6036, -6.0911, 107.11)  # south, west, north, east


def main():
    print(f"Loading LISA: {LISA}")
    lisa = gpd.read_file(str(LISA))
    print(f"  N segments: {len(lisa):,}")

    # Keep everything in WGS84; centroid warning is fine for Points (no-op).
    south, west, north, east = BBOX
    bbox = (west, south, east, north)

    def _to_point_gdf(gdf):
        """Reduce mixed Point/Polygon GDF to Points, projecting only as needed."""
        # Project to UTM for accurate centroid, then back to WGS84 for plotting
        gdf = gdf.copy()
        utm = gdf.estimate_utm_crs() if len(gdf) else gdf.crs
        polys = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(polys):
            polys = polys.to_crs(utm)
            polys["geometry"] = polys.geometry.centroid
            polys = polys.to_crs("EPSG:4326")
            pts = gdf[gdf.geometry.geom_type == "Point"]
            gdf = pd.concat([pts, polys], ignore_index=False)
        return gdf

    print("Fetching MRT/rail stations from OSM...")
    try:
        rail = ox.features_from_bbox(bbox=bbox, tags={"railway": "station"})
        rail = rail[rail.geometry.geom_type.isin(["Point", "Polygon", "MultiPolygon"])]
        rail = _to_point_gdf(rail)
        op = rail.get("operator", pd.Series([""] * len(rail))).astype(str).fillna("")
        name = rail.get("name", pd.Series([""] * len(rail))).astype(str).fillna("")
        mrt_op = op.str.contains("MRT Jakarta|LRT Jakarta|KCI|Kereta Commuter|PT MRT|PT LRT",
                                  case=False, na=False)
        mrt_name = name.str.contains(
            r"\bMRT\b|\bLRT\b|Bundaran HI|Dukuh Atas|Setiabudi|Bendungan Hilir|Senayan|"
            r"Istora|Lebak Bulus|Fatmawati|Cipete|Haji Nawi|Blok M|Blok A|ASEAN",
            case=False, na=False, regex=True)
        rail_mrt = rail[mrt_op | mrt_name]
        print(f"  MRT/LRT stations (filtered): {len(rail_mrt)}")
    except Exception as e:
        print(f"  WARN: rail fetch failed: {e}")
        rail_mrt = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    print("Fetching TransJakarta BRT stops from OSM...")
    try:
        bus = ox.features_from_bbox(bbox=bbox, tags={
            "highway": "bus_stop",
            "amenity": "bus_station",
            "public_transport": ["stop_position", "platform", "station"],
        })
        bus = bus[bus.geometry.geom_type.isin(["Point", "Polygon", "MultiPolygon"])]
        bus = _to_point_gdf(bus)
        op  = bus.get("operator", pd.Series([""] * len(bus))).astype(str).fillna("")
        net = bus.get("network",  pd.Series([""] * len(bus))).astype(str).fillna("")
        # TRUE strict: require *exactly* TransJakarta tag, not "Halte" (= bus stop generic)
        mask = (op.str.contains(r"Transjakarta|Trans Jakarta|PT TransJakarta",
                                case=False, na=False, regex=True) |
                net.str.contains(r"Transjakarta|Trans Jakarta", case=False, na=False, regex=True))
        bus_tj = bus[mask]
        print(f"  TransJakarta BRT stops (strict): {len(bus_tj)}")
    except Exception as e:
        print(f"  WARN: bus fetch failed: {e}")
        bus_tj = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    # Plot — emphasize hotspots, de-emphasize everything else
    print("Rendering figure...")
    fig, ax = plt.subplots(figsize=(12, 9))

    # NS segments very faint background
    ns = lisa[lisa["lisa_cluster"] == "NS"]
    if len(ns) > 0:
        ns.plot(ax=ax, color="#dddddd", linewidth=0.2, alpha=0.4,
                label=f"NS (not significant, {len(ns):,})")

    # Coldspots / outliers thin and muted
    for cat, color in [("LL", "#a6cee3"), ("LH", "#cab2d6"), ("HL", "#fdbf6f")]:
        sub = lisa[lisa["lisa_cluster"] == cat]
        if len(sub) == 0:
            continue
        sub.plot(ax=ax, color=color, linewidth=0.45, alpha=0.7,
                 label=f"{cat} ({len(sub):,})")

    # HH hotspots: thick and bright
    hh = lisa[lisa["lisa_cluster"] == "HH"]
    if len(hh) > 0:
        hh.plot(ax=ax, color="#d62728", linewidth=1.5, alpha=0.95, zorder=5,
                label=f"HH hotspot ({len(hh):,})")

    # MRT stations: large blue squares
    if len(rail_mrt) > 0:
        rail_mrt.plot(ax=ax, color="#1f3f8f", marker="s", markersize=110,
                      edgecolor="white", linewidth=1.5, zorder=20,
                      label=f"MRT/LRT/commuter rail station ({len(rail_mrt)})")
    # TransJakarta: medium green diamonds
    if len(bus_tj) > 0:
        bus_tj.plot(ax=ax, color="#2ca02c", marker="D", markersize=22,
                    edgecolor="white", linewidth=0.4, zorder=15, alpha=0.9,
                    label=f"TransJakarta BRT stop ({len(bus_tj)})")

    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Jakarta evening-peak congestion hotspots with mass-transit access\n"
                 "(LISA cluster classification at $p<0.05$; transit features from OpenStreetMap)",
                 fontsize=12)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=8)
    ax.grid(alpha=0.2)

    plt.tight_layout()
    plt.savefig(FIG, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved: {FIG}")


if __name__ == "__main__":
    main()
