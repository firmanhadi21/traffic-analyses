# FOSS4G 2026 Paper: Spatiotemporal Dynamics of Traffic Congestion

## Paper Overview

**Title**: Spatiotemporal Dynamics of Traffic Congestion Hotspots: A LISA Markov Analysis of Indonesian Cities Using Open-Source Geospatial Tools

**Target Conference**: FOSS4G Hiroshima 2026 - Academic Track

**Focus**: Demonstrating how PySAL ecosystem tools (esda, libpysal, giddy) can reveal spatiotemporal patterns in urban traffic congestion.

## Research Questions

1. How persistent are traffic congestion hotspots across different time periods?
2. Do neighboring road segments influence each other's congestion transitions (spatial contagion)?
3. How do spatiotemporal congestion dynamics differ across cities of varying sizes?

## Data

- **Source**: HERE Traffic API (jam_factor metric, 0-10 scale)
- **Cities**: Jakarta (14,549 segments), Bandung (3,069 segments), Semarang (1,076 segments)
- **Temporal Coverage**: 8 daily periods
  - night (00:00-06:00)
  - morning_peak (06:00-09:00)
  - morning_offpeak (09:00-11:00)
  - lunch_hours (11:00-13:00)
  - afternoon_offpeak (13:00-16:00)
  - evening_peak (16:00-19:00)
  - evening_offpeak (19:00-21:00)
  - late_night (21:00-24:00)

## Methodology

### Step 1: LISA Classification

Local Indicators of Spatial Association (LISA) computed for each road segment in each time period:

- **Tool**: `esda.Moran_Local` from PySAL
- **Spatial Weights**: K-Nearest Neighbors (k=8) from `libpysal.weights.KNN`
- **Significance**: 999 permutations, α = 0.05

**LISA Categories**:
| Code | Label | Meaning |
|------|-------|---------|
| HH | High-High | Congestion hotspot (high value surrounded by high values) |
| LL | Low-Low | Congestion coldspot (low value surrounded by low values) |
| HL | High-Low | Spatial outlier (high surrounded by low) |
| LH | Low-High | Spatial outlier (low surrounded by high) |
| NS | Not Significant | No significant spatial autocorrelation |

### Step 2: Classic Markov Chain

Transition probability matrix computed for LISA category changes between consecutive time periods:

- **Tool**: `giddy.markov.Markov`
- **States**: {NS, HH, LL, LH, HL} encoded as {0, 1, 2, 3, 4}
- **Output**: 5×5 transition matrix, steady-state distribution

### Step 3: Spatial Markov Chain

Tests whether transition probabilities depend on neighbors' states (spatial contagion):

- **Tool**: `giddy.markov.Spatial_Markov`
- **Hypothesis**: H0 = Transition probabilities are spatially homogeneous
- **Test**: Chi-squared test for spatial dependence

## Scripts

### compute_lisa_all_periods.py

Computes LISA for all 24 GeoPackage files (3 cities × 8 periods).

```bash
python compute_lisa_all_periods.py
```

**Output**:
- `lisa_results/{city}_{period}_lisa.gpkg` - Individual LISA results
- `lisa_results/{city}_combined_lisa.gpkg` - Combined for Markov analysis
- `lisa_results/lisa_summary_all_periods.csv` - Summary statistics

### compute_lisa_markov.py

Performs LISA Markov and Spatial Markov analysis.

```bash
python compute_lisa_markov.py
```

**Output**:
- `figures/markov/{city}_transition_matrix.png` - Per-city heatmaps
- `figures/markov/steady_state_comparison.png` - City comparison
- `figures/markov/diagonal_dominance.png` - Persistence comparison
- `figures/markov/spatial_contagion_test.png` - Spatial contagion results
- `figures/markov/persistence_analysis.png` - Temporal persistence
- `markov_results/markov_summary.csv` - Numerical results
- `markov_results/markov_analysis_report.txt` - Full text report

## Key Results

### 1. Hotspot Persistence (Diagonal Dominance)

| City | P(HH→HH) | P(LL→LL) | P(NS→NS) |
|------|----------|----------|----------|
| Jakarta | 6.5% | 6.1% | 90.4% |
| Bandung | 12.0% | 10.9% | 90.8% |
| Semarang | 18.8% | 25.1% | 93.6% |

**Finding**: Smaller cities (Semarang) show higher congestion persistence. Once a segment becomes congested, it tends to remain congested longer. Jakarta's hotspots are most volatile, possibly due to more complex traffic dynamics.

### 2. Steady-State Distribution

All cities converge to ~90% NS, with significant clusters (HH, LL, HL, LH) each representing 2-3% of segments in the long run.

### 3. Spatial Contagion

Chi-squared tests for spatial homogeneity:

| City | χ² (max) | p-value | Conclusion |
|------|----------|---------|------------|
| Jakarta | 2.54 | 0.111 | Weak evidence |
| Bandung | 8.43 | 0.004 | Strong evidence |
| Semarang | 6.48 | 0.011 | Evidence |

**Finding**: Bandung and Semarang show statistically significant spatial contagion - a segment's transition probability depends on its neighbors' states. This suggests congestion "spreads" between adjacent road segments.

## Dependencies

```
esda>=2.5.0
libpysal>=4.9.0
giddy>=2.3.0
geopandas>=0.14.0
matplotlib>=3.8.0
seaborn>=0.13.0
numpy>=1.24.0
pandas>=2.0.0
```

Install with:
```bash
pip install esda libpysal giddy geopandas matplotlib seaborn
```

## Reproducibility

```bash
# Step 1: Compute LISA for all periods
python compute_lisa_all_periods.py

# Step 2: Run Markov analysis
python compute_lisa_markov.py

# Results will be in:
# - lisa_results/
# - markov_results/
# - figures/markov/
```

## Paper Structure (Draft)

1. **Introduction**
   - Traffic congestion as urban challenge
   - Need for spatiotemporal analysis
   - Role of FOSS4G tools

2. **Related Work**
   - LISA and spatial autocorrelation
   - Markov chains in geography
   - Traffic hotspot studies

3. **Methodology**
   - Study area and data
   - LISA computation
   - Classic and Spatial Markov

4. **Results**
   - LISA classification patterns
   - Transition probabilities
   - Spatial contagion evidence
   - City comparisons

5. **Discussion**
   - Policy implications
   - Tool recommendations
   - Limitations

6. **Conclusion**
   - PySAL ecosystem effectiveness
   - Future work

## Figures for Paper

1. **Study Area Map**: Three cities with road networks
2. **LISA Maps**: Example period showing HH/LL clusters
3. **Transition Matrices**: Heatmaps for each city
4. **Steady-State Comparison**: Bar chart
5. **Persistence Analysis**: Diagonal dominance comparison
6. **Spatial Contagion**: Chi-squared test results

## Abstract (Draft)

Understanding the spatiotemporal dynamics of traffic congestion is critical for urban transportation planning. This study applies Local Indicators of Spatial Association (LISA) Markov analysis to examine congestion hotspot persistence and spatial contagion across three Indonesian cities: Jakarta, Bandung, and Semarang. Using the PySAL ecosystem (esda, libpysal, giddy), we analyze 264 million traffic observations across 8 daily time periods. Our findings reveal that smaller cities exhibit higher hotspot persistence, with Semarang showing 18.8% probability of congestion hotspot retention compared to Jakarta's 6.5%. Spatial Markov analysis provides evidence of spatial contagion in Bandung (χ²=8.43, p=0.004) and Semarang (χ²=6.48, p=0.011), indicating that congestion transitions depend on neighboring segment states. This work demonstrates the effectiveness of open-source geospatial tools for urban traffic analysis and provides insights for targeted congestion mitigation strategies.

**Keywords**: LISA, Markov chain, spatial contagion, traffic congestion, PySAL, FOSS4G
