# Manuscript Comparison: `trip_manuscript.tex` vs `trip_manuscript_rev.tex`

> Generated 2026-03-20. Compares the original Elsevier-formatted submission with the revised manuscript after OSM-based re-aggregation.

---

## 1. Document Format

| Feature | Original (`trip_manuscript.tex`) | Revised (`trip_manuscript_rev.tex`) |
|---------|----------------------------------|-------------------------------------|
| Document class | `elsarticle` `[review,authoryear]` | `article` `[12pt,a4paper]` |
| Target journal | Transportation Research Interdisciplinary Perspectives | Not specified |
| Line numbers | Yes (`lineno`) | No |
| Spacing | Single | 1.5× |
| Margins | Default elsarticle | 2.5 cm (`geometry`) |
| Bibliography | External `.bib` via `elsarticle-harv` | Embedded `thebibliography` (54 refs) |
| Table style | `\caption{}` at top | Bold `\textbf{Table~N.}` prefix above |

---

## 2. Data Scope

| Metric | Original | Revised | Change |
|--------|----------|---------|--------|
| Collection period | Mar 2025 – Feb 2026 (11 mo) | Mar 2025 – Mar 2026 (12 mo) | +1 month |
| Total files | 42,390 | 50,666 | +19.5% |
| Total observations | 264,936,224 | 316,586,376 | +19.5% |
| Jakarta segments | 14,549 | 14,912 | +363 |
| Bandung segments | 3,069 | 2,918 | −151 |
| Semarang segments | 1,076 | 1,047 | −29 |
| Segment matching | Centroid proximity (85% within 50 m, median 20 m) | Two-stage OSM spatial matching (99.8% match, median <1.5 m) |

The segment count changes reflect the switch from HERE FID-based to OSM `osm_composite_id`-based aggregation. Some HERE segments merge onto the same OSM edge; others fall outside the OSM network.

---

## 3. Fundamental Finding Reversal: Spatial Autocorrelation

This is the single largest change between versions.

### Global Moran's I (evening peak, KNN k=8)

| City | Original | Revised |
|------|----------|---------|
| Jakarta | 0.003 (p = 0.492) — **Random** | 0.310 (p < 0.001) — **Clustered** |
| Bandung | 0.008 (p = 0.353) — **Random** | 0.291 (p < 0.001) — **Clustered** |
| Semarang | −0.004 (p = 0.837) — **Random** | 0.298 (p < 0.001) — **Clustered** |

**Interpretation shift:** From "no global spatial autocorrelation" to "moderate, highly significant positive spatial autocorrelation across all cities." The near-zero values in the original were an artefact of unstable segment identity under the legacy FID-based aggregation—different HERE snapshots assigned different FIDs to the same physical road, randomizing the spatial signal.

### LISA Cluster Participation (evening peak, p < 0.05)

| Metric | Original | Revised |
|--------|----------|---------|
| Total significant | 7–10.5% | 34–38% |
| After FDR correction | ~0% (none survive) | 18–25% |
| HH (hotspot) share | 1.8–3.0% | 9.4–12.4% |
| LL (coldspot) share | 2.1–2.4% | 17.7–23.2% |

### Getis-Ord Gi* (evening peak, p < 0.05)

| Metric | Original | Revised |
|--------|----------|---------|
| Hot spots | 3.6–4.5% | 12.6–15.6% |
| Cold spots | 4.9–5.8% | 20.0–24.0% |
| Total significant | 8.6–10.1% | 35.2–36.6% |

### Spatial Weight Sensitivity (Moran's I range across 5 weight specs)

| | Original | Revised |
|-|----------|---------|
| Range | −0.009 to +0.009 (all p > 0.05) | 0.248 to 0.378 (all p ≈ 0) |

### Period-Specific Moran's I

| | Original | Revised |
|-|----------|---------|
| Range | −0.022 to +0.016 (no period significant) | 0.176 to 0.310 (all 24 city×period combos p < 10⁻²⁷) |
| Pattern | None | Intensifies from night → evening peak |

---

## 4. Network Topology–Congestion Relationships

### Betweenness Centrality vs Jam Factor (Pearson R²)

| City | Original | Revised |
|------|----------|---------|
| Semarang | 0.0835 | 0.0040 |
| Bandung | 0.1355 | 0.0259 |
| Jakarta | 0.0639 | 0.0121 |

**Narrative text correction:** Original text claimed R² = 0.06–0.14; revised corrects to R² = 0.004–0.026. The original values appear to have conflated Pearson r with R², or reflected pre-OSM data.

### Centrality vs Absolute Speed (Pearson R²)

| | Original | Revised |
|-|----------|---------|
| All cities | < 0.003 | < 0.002 |

Remains near-zero in both versions—confirming that centrality does not predict congestion after removing the free-flow speed confound.

### Positive Control: Free-Flow Speed → Current Speed

| | Original | Revised |
|-|----------|---------|
| R² range | 0.60–0.71 | 0.60–0.71 |

**Unchanged.** The pipeline successfully detects spatial structure in road design but not in congestion.

---

## 5. POI Density–Congestion Correlations

| City | Original Spearman ρ | Revised Spearman ρ |
|------|---------------------|---------------------|
| Jakarta | 0.008 (p = 0.31) | 0.163 (p < 0.001) |
| Bandung | 0.005 (p = 0.77) | 0.282 (p < 0.001) |
| Semarang | −0.012 (p = 0.69) | 0.078 (p = 0.017) |

**Shift:** From null correlations to weak-to-moderate positive associations. Bandung shows the strongest effect. Transport-related POIs (bus stations, fuel stations) show the highest individual category correlations (ρ = 0.17–0.29) in the revised version.

---

## 6. H3 Hexagonal Robustness Check

### Hexagon Counts

| City | Res | Original | Revised |
|------|-----|----------|---------|
| Semarang | 8 | 235 | 292 |
| Semarang | 9 | 490 | 572 |
| Bandung | 8 | 517 | 571 |
| Bandung | 9 | 1,222 | 1,415 |
| Jakarta | 8 | 1,836 | 2,000 |
| Jakarta | 9 | 5,319 | 6,202 |

### Hex-Level Moran's I

| City | Res | Original | Revised |
|------|-----|----------|---------|
| Semarang | 8 | −0.081 (p = 0.087) | +0.486 (p = 0.001) |
| Semarang | 9 | +0.004 (p = 0.443) | +0.345 (p = 0.001) |
| Bandung | 8 | +0.052 (p = 0.055) | +0.227 (p = 0.001) |
| Bandung | 9 | −0.008 (p = 0.412) | +0.351 (p = 0.001) |
| Jakarta | 8 | +0.030 (p = 0.033)* | +0.247 (p = 0.001) |
| Jakarta | 9 | +0.022 (p = 0.030)* | +0.314 (p = 0.001) |

**Shift:** From "only Jakarta shows weak significance at hex scale" to "all cities show strong, ubiquitous spatial autocorrelation at all scales."

### Hex-Level POI/Centrality Correlations

| City | Res | Original POI ρ | Revised POI ρ | Original Cent ρ | Revised Cent ρ |
|------|-----|----------------|---------------|-----------------|----------------|
| Semarang | 8 | +0.077 (ns) | −0.193** | +0.053 (ns) | −0.010 (ns) |
| Bandung | 8 | +0.053 (ns) | +0.131** | +0.041 (ns) | +0.153** |
| Jakarta | 8 | +0.021 (ns) | +0.018 (ns) | −0.007 (ns) | +0.072** |

---

## 7. Multilevel Model Variance Decomposition

| City | Metric | Original | Revised |
|------|--------|----------|---------|
| Semarang | Segments | 1,056 | 922 |
| | ICC | 89.4% | 93.1% |
| | Temporal R² | 67.0% | 63.6% |
| | Spatial ΔR² | 79.1% | 64.9% |
| | β_centrality | −2,379*** | −1,570*** |
| Bandung | Segments | 3,039 | 2,583 |
| | ICC | 87.8% | 91.6% |
| | Temporal R² | 63.1% | 59.6% |
| | Spatial ΔR² | 74.0% | 57.3% |
| | β_centrality | −5,632*** | −3,972*** |
| Jakarta | Segments | 14,411 | 13,193 |
| | ICC | 89.1% | 92.4% |
| | Temporal R² | 56.5% | 51.1% |
| | Spatial ΔR² | 77.6% | 54.7% |
| | β_centrality | −27,605*** | −13,305*** |

**Key changes:**
- ICC increases 3–4 pp → more between-segment variance (cleaner segment identity)
- Temporal R² decreases 3–5 pp → still dominates but slightly less extreme
- Spatial ΔR² decreases 14–23 pp → free-flow speed explains less between-segment variance
- Centrality coefficients decrease → weaker independent topology effect

---

## 8. Unchanged Results

These tables/findings are identical or near-identical between versions:

- **Congestion summary statistics** (Table 5): Mean JF, SD, median, max — identical
- **Mean jam factor by period** (Table 6): All 24 values identical
- **ANOVA results** (Table ANOVA): F-statistics, p-values, significant pairs — identical
- **Speed validation η²** (Table speed_validation): All 12 values identical
- **Capacity–congestion comparison** (Table 13): JF means, t-stats, effect sizes — identical
- **Capacity score correlations** (Table 14): All Pearson/Spearman values — identical
- **Capacity drop proximity** (Table 15): All values — identical
- **Local bottleneck comparison** (Table 16): All values — identical
- **Positive control R²** (free-flow → speed): 0.60–0.71 — identical

---

## 9. Narrative and Interpretation Shifts

### Core Argument (preserved)
Both versions argue that **demand synchronization** (time-of-day) is the primary congestion mechanism, not network topology or road capacity.

### Spatial Clustering (reversed)
- **Original:** "Congestion is spatially random." Absence of Moran's I significance was a key finding supporting pure temporal dominance.
- **Revised:** "Congestion exhibits moderate spatial clustering (Moran's I ≈ 0.30)." Acknowledges real spatial structure but argues it is **not explained by network centrality or capacity**—instead reflecting demand-side patterns (where people want to go).

### POI Density (new finding)
- **Original:** No correlation detected.
- **Revised:** Weak-to-moderate associations (ρ = 0.08–0.28). Activity centers contribute to congestion clustering, though the effect is modest vs temporal factors.

### H3 Robustness (reversed)
- **Original:** Null findings confirmed at hex scale; only Jakarta shows weak effect.
- **Revised:** Strong spatial autocorrelation at all scales for all cities; some POI/centrality correlations emerge at neighbourhood scale (Bandung, Semarang).

### Limitations (updated)
- **Original:** Mentions "Jakarta's weak but significant neighbourhood-level spatial autocorrelation."
- **Revised:** Updates to "strong neighbourhood-level spatial autocorrelation across all three cities."

---

## 10. Root Cause of Differences

The fundamental driver of all numerical changes is the **migration from FID-based to OSM-based segment aggregation**.

Under the legacy approach, HERE Traffic API returned segments with inconsistent Feature IDs across snapshots. When aggregating 50,000+ files, this meant that the "same" physical road could receive different FIDs in different collection cycles, effectively **randomizing the spatial signal**. This produced:
- Near-zero Moran's I (spatial signal destroyed by ID scrambling)
- Low LISA participation (genuine clusters diluted)
- Inflated centrality–jam factor R² (noise in both variables creates spurious correlations)
- Null POI correlations (signal-to-noise too low)

The OSM-based pipeline assigns each HERE segment a stable `osm_composite_id` via two-stage spatial matching (intersection + nearest-neighbour), ensuring consistent identity across all collection cycles. This **recovers the true spatial signal**, revealing:
- Moderate spatial autocorrelation that was always present in the physical system
- Genuine local clustering patterns
- True (weak) centrality effects
- Detectable POI density associations

---

## 11. Summary

| Finding | Original | Revised | Direction |
|---------|----------|---------|-----------|
| Spatial autocorrelation | None (I ≈ 0.003) | Moderate (I ≈ 0.30) | **Reversed** |
| LISA clusters | ~10% (none after FDR) | 34–38% (18–25% after FDR) | **3–4× increase** |
| Centrality → jam factor R² | 0.06–0.14 | 0.004–0.026 | **5–6× decrease** |
| Centrality → speed R² | < 0.003 | < 0.002 | Unchanged (null) |
| POI → congestion ρ | ~0 (null) | 0.08–0.28 | **New finding** |
| Temporal R² (multilevel) | 57–67% | 51–64% | Slight decrease |
| Positive control R² | 0.60–0.71 | 0.60–0.71 | Unchanged |
| Core argument | Demand synchronization dominates | Demand synchronization dominates | **Preserved** |

The revised manuscript **maintains the core demand-synchronization argument** but presents a more nuanced picture: spatial clustering exists and is real, but it operates through demand-side mechanisms (activity centers, commuting patterns) rather than supply-side factors (network topology, road capacity). This is a stronger and more defensible position than the original's claim of complete spatial randomness.
