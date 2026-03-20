# Manuscript Comparison: trip_manuscript.tex vs firmanhadi_ceus_v2.tex

## Summary of Framing Differences

These are **two different versions of the same underlying research** with significant framing differences:

| Aspect | firmanhadi_ceus_v2.tex | trip_manuscript.tex |
|--------|------------------------|---------------------|
| **Target Journal** | Computers, Environment and Urban Systems (CEUS) | Transportation Research Part A or similar |
| **Research Framing** | "Temporal factors dominate spatial factors by 1,000-4,000x" | "Demand synchronization" - millions commuting simultaneously |
| **Effect Size Reporting** | η² = 15-24% for time-of-day | 57-67% of within-segment speed fluctuations |
| **Methodological Emphasis** | Geostatistics, jam factor analysis, Python pipeline | Multilevel mixed-effects models, cross-metric validation |
| **Structure** | Has separate **Literature Review** section | No separate Literature Review |
| **Bottleneck Section** | Dedicated subsection before Python Package | Integrated after Multilevel Variance Decomposition |
| **Positive Control** | Not explicitly highlighted | Explicit "positive-control methodology" section |
| **Cross-Metric Validation** | Not mentioned | Explicit validation using absolute speed, jam factor, speed reduction |

---

## 1. Title and Authors

### firmanhadi_ceus_v2.tex
```tex
\title{Spatiotemporal Analysis of Urban Traffic Congestion, Network Topology, and Capacity Constraints in Indonesian Metropolitan Cities}

\author{%
  Firman Hadi\textsuperscript{1,*} \and
  Yasser Wahyuddin\textsuperscript{1} \and
  L.M. Sabri\textsuperscript{1} \and
  Agung Indrajit\textsuperscript{2}%
}
```

### trip_manuscript.tex
No title/author section (prepared for journal submission without it).

---

## 2. Abstract (Core Framing Differences)

### firmanhadi_ceus_v2.tex
> Urban traffic congestion presents major challenges to sustainable growth in rapidly growing Southeast Asian cities. This study provides a spatiotemporal analysis of traffic congestion in three Indonesian metropolitan areas—Jakarta, Bandung, and Semarang—using high-resolution traffic flow data from the HERE Traffic API over 11 months (March 2025 to February 2026), totaling over 264 million observations across 18,694 road segments. We introduce an open-source Python package delivering an end-to-end traffic analysis pipeline—from API data collection to geostatistical analysis, HPC-enabled network centrality calculations, and automated manuscript creation. The methodology combines jam factor analysis with geostatistical tools (Moran's I, LISA, Getis-Ord Gi*), OpenStreetMap network analysis using OSMnx, and a novel graph-based capacity drop detection framework. **Our central finding is that temporal factors dominate spatial factors by 1,000--4,000×**: time-of-day (η² = 15--24%) vastly outweighs network centrality, POI density, and road capacity (R² < 0.01%) in explaining congestion variance. Triangulated evidence from four independent spatial predictors all yield null results: road capacity shows negligible correlation (r < 0.04), capacity drops show no proximity effect (p = 0.10--0.83), and bottleneck gradients are indistinguishable from surrounding segments (|d| < 0.05). H3 hexagonal aggregation confirms these null findings are not modifiable areal unit artefacts. **This demonstrates that congestion is fundamentally a temporal synchronization problem**—millions of people traveling simultaneously—rather than a spatial infrastructure constraint. The evening peak shows congestion approximately 40% above daily averages. These findings support prioritizing demand management strategies alongside infrastructure expansion in rapidly urbanizing contexts.

### trip_manuscript.tex
> Urban traffic congestion is widely attributed to infrastructure bottlenecks---insufficient road capacity, poor network connectivity, or land-use mismatches---yet the relative contribution of *when* versus *where* people travel remains poorly quantified in rapidly urbanizing cities with motorcycle-dominated traffic. This study analyzes 264 million traffic observations collected at 15-minute intervals across Jakarta, Bandung, and Semarang over 11 months to empirically decompose congestion into its temporal and spatial components. Using multilevel mixed-effects models on absolute speed, we find that demand synchronization---millions of commuters traveling simultaneously---is the primary congestion mechanism: **time-of-day explains 57--67% of within-segment speed fluctuations**, while network centrality adds less than 1% beyond road type. A positive-control test confirms that the same analytical pipeline successfully detects spatial structure in road design (R² = 0.60--0.71 for free-flow speed) but not in congestion (R² < 0.003), ruling out methodological artefacts. Cross-metric validation using absolute speed, jam factor, and speed reduction confirms these patterns are not normalization artefacts. Evening peak congestion exceeds daily averages by approximately 40% across all three cities despite a 20× population range, consistent with a demand-driven rather than supply-constrained mechanism. These findings imply that demand management interventions (congestion pricing, flexible work schedules, public transit) may yield greater returns than capacity expansion alone in rapidly urbanizing contexts.

### Key Abstract Differences

| Element | firmanhadi_ceus_v2 | trip_manuscript |
|---------|-------------------|-----------------|
| Opening frame | "sustainable growth in Southeast Asian cities" | "widely attributed to infrastructure bottlenecks" |
| Data description | "spatiotemporal analysis" | "empirically decompose congestion into temporal and spatial components" |
| Central finding | "temporal factors dominate by 1,000-4,000×" | "demand synchronization is the primary mechanism" |
| Effect size | η² = 15-24% | 57-67% of within-segment speed fluctuations |
| Method emphasis | Python package, geostatistical tools | multilevel mixed-effects models on absolute speed |
| Validation | "triangulated evidence from four independent spatial predictors" | "positive-control test", "cross-metric validation" |
| Framing conclusion | "temporal synchronization problem" | "demand-driven rather than supply-constrained" |

---

## 3. Keywords

### firmanhadi_ceus_v2.tex
```tex
Keywords: Urban traffic congestion; Spatiotemporal analysis; Network centrality; Jam factor; Capacity bottleneck; Indonesian cities; HERE Traffic API; OSMnx; Spatial autocorrelation
```

### trip_manuscript.tex
```tex
Keywords: Urban traffic congestion; Spatiotemporal analysis; Demand synchronization; Network centrality; Multilevel model; Indonesian cities; OpenStreetMap
```

---

## 4. Introduction - Contributions Section

### firmanhadi_ceus_v2.tex
> This study addresses gaps with four methods: analyzing 11 months of traffic data totaling over 264 million observations; using geostatistical techniques like Moran's I, LISA, and Getis-Ord Gi* to identify clusters; applying OSMnx network analysis to link topology and congestion; and testing if capacity constraints, including a new graph-based capacity drop detection, predict congestion. **The research offers five key contributions:** a comprehensive open-source Python software package for traffic analysis; a methodology integrating commercial traffic data with open-source network analysis; a first systematic comparison of three Indonesian cities showing null results across four spatial predictors; insights that normalized congestion metrics remove capacity effects, impacting capacity–congestion studies; and practical recommendations for traffic management in Southeast Asian cities.

### trip_manuscript.tex
> This study addresses gaps with four methods: analyzing 11 months of traffic data totaling over 264 million observations; using geostatistical techniques like Moran's I, LISA, and Getis-Ord Gi* to identify clusters; applying OSMnx network analysis to link topology and congestion; and testing if capacity constraints, including a new graph-based capacity drop detection, predict congestion. **The research offers five key contributions:** (1) empirical evidence that urban congestion operates as a demand synchronization phenomenon, with time-of-day explaining 57--67% of speed variation while network topology adds less than 1% beyond road type; (2) a positive-control methodology demonstrating that the same analytical pipeline detects spatial structure in road design but not in congestion, ruling out methodological artefacts; (3) cross-metric validation showing results hold for absolute speed, not only normalized jam factor, addressing the circularity inherent in capacity-normalized congestion metrics; (4) a comprehensive open-source Python pipeline integrating commercial traffic data with network analysis; and (5) practical evidence supporting demand management over capacity expansion in motorcycle-dominated Southeast Asian cities.

---

## 5. Structure: Separate Literature Review Section

### firmanhadi_ceus_v2.tex has a dedicated Literature Review section:
```tex
\section{Literature Review}

Traffic congestion in developing countries has unique characteristics, including high
variability, distinct peak times, and a strong reliance on informal transportation...
[several paragraphs summarizing literature]
```

### trip_manuscript.tex
No separate Literature Review section - the literature is woven into the Introduction.

---

## 6. Methodology Differences

### Temporal Pattern Analysis

### firmanhadi_ceus_v2.tex
> Temporal patterns were examined by calculating summary statistics for each period across all road segments. One-way ANOVA tested for significant differences between periods, with post-hoc Tukey HSD tests identifying specific significant pairs.

### trip_manuscript.tex
> Temporal patterns were examined by calculating summary statistics for each period across all road segments. One-way ANOVA tested for significant differences between periods, with post-hoc Tukey HSD tests identifying specific significant pairs. **To validate that temporal effects are not an artifact of jam factor normalization, ANOVA was also conducted on absolute speed (km/h), speed reduction (free-flow minus current speed, km/h), and free-flow speed, enabling cross-metric comparison of effect sizes (η²).**

---

## 7. Section Ordering Difference

### firmanhadi_ceus_v2.tex order:
1. Temporal Pattern Analysis
2. Geostatistical Analysis
3. Spatial Scale Sensitivity (H3)
4. Network Centrality Analysis
5. **Bottleneck and Capacity Drop Analysis**
6. **Python Package and Computational Pipeline**

### trip_manuscript.tex order:
1. Temporal Pattern Analysis
2. Geostatistical Analysis
3. Spatial Scale Sensitivity (H3)
4. Network Centrality Analysis
5. **Multilevel Variance Decomposition**
6. **Bottleneck and Capacity Drop Analysis**
7. Open-Source Analysis Pipeline

---

## 8. Statistical Results Difference

### firmanhadi_ceus_v2.tex
> One-way ANOVA confirms that temporal period differences are highly statistically significant... The effect size (η²) ranges from **15--24%**---a strong effect for a single categorical variable.

### trip_manuscript.tex
> One-way ANOVA confirms that temporal period differences are highly statistically significant... The effect size (η²) ranges from **8--10% for jam factor and speed reduction, 5--6% for absolute speed**, and effectively zero for free-flow speed.

---

## 9. Betweenness Centrality Subsection

### firmanhadi_ceus_v2.tex
> Correlation analysis reveals **negligible correlations** between betweenness centrality and jam factor across all cities. Despite Bandung's statistically significant Spearman ρ = 0.040 (p = 0.009), the effect size is trivially small.

### trip_manuscript.tex
> The results reveal a striking pattern: centrality shows moderate correlations with jam factor (R² = 0.06--0.14) and speed reduction (R² = 0.07--0.13), but **near-zero correlations with absolute current speed** (R² < 0.003). This divergence arises because jam factor and speed reduction both incorporate free-flow speed normalization, while absolute speed does not.

**trip_manuscript.tex adds a "Positive Control: Free-Flow Speed as Spatial Predictor" paragraph** that explains why the pipeline detects spatial structure in free-flow speed (R² = 0.60-0.71) but not congestion.

---

## 10. Figure References Difference

### firmanhadi_ceus_v2.tex
Bandung and Semarang hotspot figures are referenced inline:
> \textbf{Bandung} hotspots include the Dago/Setiabudhi northern corridors... (Figure~\ref{fig:bdg_hotspots}). \textbf{Semarang} hotspots appear... (Figure~\ref{fig:smg_hotspots}).

### trip_manuscript.tex
Bandung and Semarang hotspots reference supplementary figures:
> \textbf{Bandung} hotspots include... (Supplementary Figure~S1). \textbf{Semarang} hotspots appear... (Supplementary Figure~S2).

---

## Summary: Key Framing Themes

| Theme | firmanhadi_ceus_v2 | trip_manuscript |
|-------|-------------------|-----------------|
| **Problem framing** | Data gap in Indonesia; sustainable growth challenges | Infrastructure bottleneck attribution vs. demand timing |
| **Central mechanism** | Temporal dominance (1,000-4,000×) | Demand synchronization |
| **Novelty emphasis** | Python package; novel graph-based capacity drop | Positive-control methodology; cross-metric validation |
| **Effect size** | η² = 15-24% | 57-67% variance explained |
| **Methodological story** | Triangulated null results from 4 spatial predictors | Pipeline validated via positive control |
| **Journal fit** | Geography/Urban Planning (CEUS) | Transportation Research (TR Part A) |
