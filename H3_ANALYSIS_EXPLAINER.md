# H3 Hexagonal Aggregation — Robustness Check Explainer

## Why We Did This

The segment-level analysis found no correlation between traffic congestion (jam factor)
and any spatial predictor — POI density, network centrality, road capacity, or capacity
drop proximity. Two explanations were possible:

1. **The null result is real** — congestion is genuinely not driven by these spatial factors
2. **Scale mismatch** — the predictors operate at a neighbourhood scale, but individual
   road segments are too fine-grained to capture that signal (Modifiable Areal Unit Problem)

H3 aggregation tests explanation 2. By binning all variables into the same hexagonal
spatial units, we align the measurement scale of dependent and independent variables.

---

## What the Script Does (`h3_robustness_check.py`)

1. Assign each road segment centroid to an H3 hex cell at resolutions 8 and 9
2. Aggregate `jam_factor_mean` per hexagon — observation-weighted mean across all 8 time
   periods and all segments that fall inside the hex
3. Fetch POIs from OSM (same tags as `poi_congestion_analysis.py`), count per hexagon
4. Download OSM drive network, compute edge betweenness centrality, average per hexagon
5. Run Pearson + Spearman correlations at the hex level
6. Run Global Moran's I on hex-aggregated congestion
7. Compare all results against existing segment-level benchmarks

### H3 Resolutions Tested

| Resolution | Hex diameter | Hex area | Spatial concept |
|---|---|---|---|
| 8 | ~461 m | ~0.46 km² | Neighbourhood scale |
| 9 | ~174 m | ~0.10 km² | Block scale |

---

## What the Output Contains

### Terminal Output
A comparison table across all 6 combinations (3 cities × 2 resolutions) showing:
- POI density correlation (Pearson r, Spearman ρ, p-value)
- Network centrality correlation (Pearson r, Spearman ρ, p-value)
- Global Moran's I and p-value

Followed by an interpretation block.

### Files Saved

| File | Contents |
|---|---|
| `analysis_results/h3_robustness_results.csv` | Full correlation table, all cities × resolutions |
| `analysis_results/h3_r8_smg.gpkg` | Hex GeoPackage — Semarang, resolution 8 |
| `analysis_results/h3_r9_smg.gpkg` | Hex GeoPackage — Semarang, resolution 9 |
| `analysis_results/h3_r8_bdg.gpkg` | Hex GeoPackage — Bandung, resolution 8 |
| `analysis_results/h3_r9_bdg.gpkg` | Hex GeoPackage — Bandung, resolution 9 |
| `analysis_results/h3_r8_jkt.gpkg` | Hex GeoPackage — Jakarta, resolution 8 |
| `analysis_results/h3_r9_jkt.gpkg` | Hex GeoPackage — Jakarta, resolution 9 |

Each GeoPackage contains per-hexagon: geometry, weighted mean jam factor, POI count,
mean betweenness centrality. Directly mappable in QGIS or GeoPandas.

---

## Actual Results (Run: 2026-03-03)

### Full Results Table

**Resolution 8 (~461 m hex diameter):**

| City | Hexes | POI r | POI ρ | POI p | Cent r | Cent ρ | Cent p | Moran's I | p |
|---|---|---|---|---|---|---|---|---|---|
| Semarang | 235 | +0.048 | +0.077 | 0.242 | +0.054 | +0.053 | 0.427 | −0.081 | 0.087 |
| Bandung | 517 | −0.002 | +0.053 | 0.228 | +0.002 | +0.041 | 0.352 | +0.052 | 0.055 |
| Jakarta | 1,836 | +0.012 | +0.021 | 0.362 | −0.038 | −0.007 | 0.784 | +0.030 | **0.033*** |

**Resolution 9 (~174 m hex diameter):**

| City | Hexes | POI r | POI ρ | POI p | Cent r | Cent ρ | Cent p | Moran's I | p |
|---|---|---|---|---|---|---|---|---|---|
| Semarang | 490 | +0.018 | +0.033 | 0.462 | +0.012 | +0.022 | 0.630 | +0.004 | 0.443 |
| Bandung | 1,222 | −0.009 | +0.027 | 0.339 | +0.026 | +0.053 | 0.070 | −0.008 | 0.412 |
| Jakarta | 5,319 | −0.028 | −0.014 | 0.314 | +0.088 | −0.003 | 0.836 | +0.022 | **0.030*** |

(*\* p < 0.05*)

**OSM data fetched during run:**
- Semarang: 5,855 POIs; network 63,325 nodes / 161,372 edges
- Bandung: 8,119 POIs; network 97,450 nodes / 227,781 edges
- Jakarta: 35,231 POIs; network 315,980 nodes / 753,746 edges

---

### Outcome: A + partial C

**POI density — Outcome A (null persists)**
All correlations remain near zero (|ρ| < 0.08) and non-significant (all p > 0.22)
at both resolutions across all three cities. Scale mismatch was NOT the cause of
the null finding. Congestion is genuinely unrelated to activity centre density.

**Network centrality — Outcome A (null persists)**
All correlations trivially small (|ρ| < 0.06) and non-significant (all p > 0.07)
at both resolutions. The null segment-level finding is not a MAUP artefact.

**Moran's I — partial Outcome C (Jakarta only)**
Jakarta shows weak but consistent spatial autocorrelation at the neighbourhood
scale at both resolutions:
- Resolution 8: I = +0.030, p = 0.033
- Resolution 9: I = +0.022, p = 0.030

This was invisible at segment level (I = +0.0026, p = 0.492). H3 aggregation
reduces within-hex noise, revealing that Jakarta's congestion has weak but coherent
neighbourhood-level spatial structure. Importantly, this clustering is NOT explained
by POI density or centrality — both remain null.

Semarang and Bandung show no significant Moran's I at either resolution.

---

## Known Limitations of This Robustness Check

### 1. Jam factor normalisation is not fixed here
Jam factor (JF = 1 − v/v_freeflow) is normalised to each segment's own free-flow
speed. This removes absolute capacity information regardless of aggregation scale.
H3 aggregation cannot recover the capacity signal. A proper capacity test requires
replacing JF with absolute delay (seconds per km).

### 2. Centrality uses k-sample approximation for large networks
Networks are much larger than anticipated (Jakarta: 753,746 edges; Bandung: 227,781
edges; Semarang: 161,372 edges). All three used k=500 sampled nodes for betweenness
centrality, introducing sampling noise. Full exact computation would require HPC.

### 3. Two resolutions may not span the full range
Resolutions 7 (~1.2 km²) and 10 (~0.015 km²) were not tested. If a relationship
only appears at very coarse or very fine scale, this check would miss it.

### 4. POI fetch is live (OSM API)
Results depend on current OSM data, not a snapshot from the study period.
Changes in OSM coverage since data collection could affect POI counts.

---

## Segment-Level Baseline (Existing Analysis)

For comparison against the hex-level results:

| Variable | Semarang | Bandung | Jakarta | All p-values |
|---|---|---|---|---|
| POI Spearman ρ | −0.007 | −0.013 | −0.0005 | > 0.6 |
| Centrality Spearman ρ | −0.011 | +0.012 | +0.002 | > 0.44 |
| Global Moran's I | −0.0039 | +0.0075 | +0.0026 | > 0.35 |

Temporal ANOVA (η²): 15–24% across cities — dominant predictor at any spatial scale.

---

## How to Cite in the Paper

See `ROBUSTNESS_PARAGRAPH.md` for the full drafted paragraph ready for insertion
into the manuscript. The key sentences are:

> To address the potential modifiable areal unit problem (MAUP), we aggregated all
> variables into Uber H3 hexagonal bins at resolutions 8 (~461 m hex diameter,
> ~0.46 km² area) and 9 (~174 m, ~0.10 km²) and re-ran all correlations at the
> neighbourhood scale. POI-density and centrality correlations remained near zero
> at both resolutions (all |ρ| < 0.08, p > 0.07), confirming that the null
> segment-level findings are not an artefact of spatial scale. In Jakarta alone,
> hex-level Moran's I reached statistical significance (I = 0.030, p = 0.033 at
> resolution 8; I = 0.022, p = 0.030 at resolution 9), suggesting weak but coherent
> neighbourhood-scale congestion structure that is not detectable at the individual
> road-segment level and is not explained by the predictors tested.
