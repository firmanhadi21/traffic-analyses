# Spatiotemporal Dynamics of Traffic Congestion Hotspots: A LISA Markov Analysis of Indonesian Cities Using Open-Source Geospatial Tools

**Firman Hadi¹\*, Fauzan Abdullah², Yasser Wahyuddin¹, L.M. Sabri¹**

¹ Department of Geodetic Engineering, Universitas Diponegoro, Semarang, Indonesia  
² Department of Statistics, Faculty of Sciences and Mathematics, Universitas Diponegoro, Semarang, Indonesia

\* Corresponding Author: firmanhadi21@lecturer.undip.ac.id

---

## Abstract

Understanding the spatiotemporal dynamics of traffic congestion is critical for urban transportation planning. This study applies Local Indicators of Spatial Association (LISA) Markov analysis to examine congestion hotspot persistence and spatial contagion across three Indonesian cities: Jakarta, Bandung, and Semarang. Using the PySAL ecosystem (esda, libpysal, giddy), we analyze 264 million traffic observations across 8 daily time periods. Our findings reveal that smaller cities exhibit higher hotspot persistence, with Semarang showing 18.8% probability of congestion hotspot retention compared to Jakarta's 6.5%. Spatial Markov analysis provides evidence of spatial contagion in Bandung (χ²=8.43, p=0.004) and Semarang (χ²=6.48, p=0.011), indicating that congestion transitions depend on neighboring segment states. This work demonstrates the effectiveness of open-source geospatial tools for urban traffic analysis and provides insights for targeted congestion mitigation strategies.

**Keywords**: LISA, Markov chain, spatial contagion, traffic congestion, PySAL, FOSS4G

---

## 1. Introduction

Traffic congestion remains one of the most pressing challenges facing rapidly urbanizing regions across the developing world. In Indonesia, the economic cost of traffic congestion in Jakarta alone is estimated at USD 5 billion annually (World Bank, 2020), with significant impacts on productivity, air quality, and quality of life. Beyond economic costs, persistent congestion creates environmental and health burdens through increased vehicle emissions and prolonged travel times.

Traditional traffic analysis approaches often treat congestion as a purely temporal phenomenon, focusing on aggregate metrics like average speeds or volume-to-capacity ratios across entire road networks. However, this perspective overlooks critical spatial dimensions: congestion hotspots are not randomly distributed across urban networks, and their evolution over time exhibits both spatial clustering and temporal persistence. Understanding where congestion emerges, how it spreads between neighboring road segments, and whether certain locations experience chronic versus transient congestion is essential for designing targeted mitigation strategies.

Spatiotemporal analysis methods, particularly those rooted in exploratory spatial data analysis (ESDA), offer powerful tools for uncovering these hidden patterns. Local Indicators of Spatial Association (LISA) can identify statistically significant congestion hotspots and coldspots while accounting for spatial randomness. When combined with Markov chain analysis, these methods reveal temporal transition dynamics: whether segments tend to remain in congested states (persistence) or transition frequently between states (volatility). Furthermore, Spatial Markov analysis tests whether these transitions exhibit spatial contagion—whether a segment's likelihood of becoming congested depends on the congestion state of its neighbors.

The open-source geospatial software (FOSS4G) ecosystem has matured significantly in recent years, with Python-based tools like PySAL providing accessible, reproducible, and extensible frameworks for advanced spatial analysis. Despite this, adoption in operational traffic management contexts remains limited, particularly in developing countries where proprietary software costs pose barriers. This paper demonstrates the effectiveness of FOSS4G tools for analyzing real-world traffic data from three Indonesian cities: Jakarta (14,549 road segments), Bandung (3,069 segments), and Semarang (1,076 segments).

**Research Questions:**

1. How persistent are traffic congestion hotspots across different daily time periods?
2. Do neighboring road segments influence each other's congestion transitions (spatial contagion)?
3. How do spatiotemporal congestion dynamics differ across cities of varying sizes and network complexity?

Our contribution is fourfold: (1) We apply LISA Markov analysis to high-resolution traffic data across multiple cities and time periods, (2) We demonstrate the complete workflow using open-source tools (PySAL, GeoPandas, giddy), (3) We release a reproducible data collection and analysis pipeline as an open-source Python package (traffic-congestion-pipeline, available on PyPI), and (4) We provide actionable insights into urban congestion dynamics that can inform infrastructure planning and traffic management policies.

---

## 2. Related Work

### 2.1 Spatial Autocorrelation and LISA

Spatial autocorrelation—the tendency of nearby locations to exhibit similar values—is a fundamental concept in spatial analysis (Tobler, 1970). Moran's I statistic (Moran, 1950) provides a global measure of spatial clustering, but local indicators are needed to identify where clusters occur. Anselin (1995) formalized Local Indicators of Spatial Association (LISA), which decompose global spatial autocorrelation into local contributions, enabling identification of statistically significant hotspots (High-High clusters), coldspots (Low-Low), and spatial outliers (High-Low, Low-High).

LISA methods have been widely applied to traffic analysis. Zhang et al. (2011) identified crash hotspots using Moran's I and LISA in Toronto. Wang et al. (2013) used LISA to detect spatial clustering of traffic incidents in Shanghai. Prasannakumar et al. (2011) applied spatial autocorrelation to identify accident hotspots in Kerala, India. However, these studies primarily focus on static spatial patterns, treating time as secondary.

### 2.2 Markov Chains in Spatial Analysis

Markov chain models, which describe probabilistic transitions between states, have long been used in geography to analyze land use change (Baker, 1989), regional income convergence (Rey, 2001), and urban growth dynamics (Batty, 1976). The key assumption is that future states depend only on the current state (memoryless property), making transitions tractable to analyze through transition probability matrices.

In transportation research, Markov models have been applied to predict traffic state evolution (Li et al., 2015), analyze traffic flow transitions (Cheng et al., 2012), and forecast congestion propagation (Min & Wynter, 2011). However, these applications rarely incorporate spatial structure explicitly.

### 2.3 Spatial Markov Analysis

Rey (2001) introduced the Spatial Markov framework, which conditions transition probabilities on the spatial context—specifically, the state of neighboring locations. This enables testing for spatial contagion: whether transitions are spatially homogeneous or exhibit dependence on neighbors' states. Originally developed for regional income dynamics, Spatial Markov has been applied to urban land transitions (Zheng et al., 2013) and housing price changes (Chegut et al., 2015), but applications to traffic remain scarce.

To our knowledge, this is the first application of LISA Spatial Markov analysis to multi-city traffic congestion data, particularly in a developing country context where infrastructure constraints and rapid urbanization create unique congestion dynamics.

### 2.4 Open-Source Geospatial Tools

The PySAL (Python Spatial Analysis Library) ecosystem has become the de facto standard for spatial econometrics and exploratory spatial analysis in Python (Rey & Anselin, 2007; Rey et al., 2021). The library's modular design separates concerns:
- **libpysal**: Spatial weights and graph construction
- **esda**: Exploratory spatial data analysis (LISA, Moran's I, Getis-Ord)
- **giddy**: Spatial dynamics and Markov analysis

Combined with GeoPandas (Jordahl et al., 2020) for spatial data manipulation and Matplotlib/Seaborn for visualization, this stack provides a complete, open-source workflow for advanced spatial analysis. Our paper showcases these tools on a real-world traffic analysis problem, providing reproducible code that practitioners can adapt to other contexts.

---

## 3. Methodology

### 3.1 Study Area and Data

We analyze three Indonesian cities representing different urban scales:

| City | Population | Road Segments | Network Density | Urban Characteristics |
|------|-----------|---------------|----------------|----------------------|
| Jakarta | 10.6M | 14,549 | High | Megacity, dense network, complex travel patterns |
| Bandung | 2.5M | 3,069 | Medium | Second-tier city, mountainous terrain |
| Semarang | 1.7M | 1,076 | Low | Coastal city, less congested |

**Data Source**: Traffic data were collected from HERE Technologies Traffic API (v8) from March 2025 to February 2026. The API provides the `jam_factor` metric (0-10 scale), where 0 represents free-flow conditions and 10 indicates complete standstill. Each road segment's geometry and traffic attributes were retrieved.

**Temporal Aggregation**: We divided each day into 8 periods to capture diurnal congestion patterns:

1. **Night** (00:00-06:00): Minimal traffic
2. **Morning Peak** (06:00-09:00): Commute to work/school
3. **Morning Off-Peak** (09:00-11:00): Post-rush hour
4. **Lunch Hours** (11:00-13:00): Midday travel
5. **Afternoon Off-Peak** (13:00-16:00): Pre-rush hour
6. **Evening Peak** (16:00-19:00): Evening commute
7. **Evening Off-Peak** (19:00-21:00): Post-work activities
8. **Late Night** (21:00-24:00): Nighttime leisure

For each period, we computed the median `jam_factor` across all observations within that time window, reducing noise while preserving central tendency.

**Data Volume**: The complete dataset comprises:
- 18,694 unique road segments
- 8 time periods per day
- 149,552 spatiotemporal observations
- ~264 million traffic measurements (aggregated into medians)

### 3.2 LISA Computation

For each city-period combination, we computed Local Moran's I statistics using PySAL's `esda.Moran_Local` class:

```python
from esda import Moran_Local
from libpysal.weights import KNN

# Construct K-Nearest Neighbors spatial weights (k=8)
w = KNN.from_dataframe(gdf, k=8)
w.transform = 'r'  # Row-standardization

# Compute LISA
lisa = Moran_Local(gdf['jam_factor'], w, permutations=999)
```

**Spatial Weights**: We use K-Nearest Neighbors (k=8) rather than distance-based weights because road networks exhibit irregular spacing, and KNN ensures all segments have neighbors regardless of network density.

**Permutation Testing**: Statistical significance is assessed via 999 random permutations under the null hypothesis of spatial randomness. Segments with pseudo p-values < 0.05 are classified as significant.

**LISA Categories**: Each segment is assigned to one of five categories:

- **HH (High-High)**: High congestion surrounded by high congestion → **hotspot**
- **LL (Low-Low)**: Low congestion surrounded by low congestion → **coldspot**
- **HL (High-Low)**: High congestion among low neighbors → **spatial outlier**
- **LH (Low-High)**: Low congestion among high neighbors → **spatial outlier**
- **NS (Not Significant)**: No significant spatial pattern

### 3.3 Classic Markov Analysis

Given a sequence of LISA categories across the 8 time periods, we model transitions as a first-order Markov chain using `giddy.markov.Markov`:

```python
from giddy.markov import Markov

# y: (n_segments × n_periods) matrix of LISA codes
# Encoded as integers: NS=0, HH=1, LL=2, LH=3, HL=4
m = Markov(y)

# Transition probability matrix P[i,j] = P(period_t+1 = j | period_t = i)
P = m.p

# Steady-state distribution (long-run equilibrium)
steady_state = m.steady_state
```

The 5×5 transition matrix $P$ captures the probability that a segment in category $i$ at time $t$ transitions to category $j$ at time $t+1$. Diagonal elements $P_{ii}$ represent **persistence probabilities**—the likelihood a segment remains in the same state.

### 3.4 Spatial Markov Analysis

To test for spatial contagion, we condition transition probabilities on the **spatial lag**—the average state of a segment's neighbors. Using `giddy.markov.Spatial_Markov`:

```python
from giddy.markov import Spatial_Markov

# Spatial weights for conditioning
w = KNN.from_dataframe(gdf, k=8)

# Spatial Markov: transitions conditioned on lag
sm = Spatial_Markov(y, w, permutations=999)

# Chi-squared test for spatial homogeneity
# H0: Transition probabilities are independent of neighbors
chi2 = sm.chi2  # Test statistic for each lag class
```

The null hypothesis is that $P(i \to j)$ does not depend on neighbors' states. Rejection (p < 0.05) indicates **spatial contagion**: transitions are influenced by spatial context.

### 3.5 Software and Reproducibility

All analyses were performed using Python 3.11 with the following key dependencies:

- `geopandas==0.14.3`: Spatial data manipulation
- `esda==2.5.1`: LISA and Moran's I
- `libpysal==4.9.2`: Spatial weights
- `giddy==2.3.5`: Spatial Markov analysis
- `matplotlib==3.8.3`, `seaborn==0.13.2`: Visualization

**Reproducible Pipeline**: To facilitate replication and extension of this work, we developed `traffic-congestion-pipeline`, a Python package that automates the complete workflow from data collection to analysis. The package is available on PyPI:

```bash
pip install traffic-congestion-pipeline
```

This package provides command-line tools and Python APIs for:
- Multi-provider traffic data collection (HERE, TomTom, Google)
- Automated spatial aggregation and temporal binning
- LISA computation with configurable spatial weights
- Markov chain and Spatial Markov analysis
- Publication-ready visualization generation

Complete code, analysis scripts, and documentation are available at: https://github.com/firmanhadi21/traffic-analyses

---

## 4. Results

Our analysis reveals distinct spatiotemporal congestion dynamics across the three cities, with notable differences in hotspot persistence, transition volatility, and spatial contagion effects.

### 4.1 LISA Spatial Clustering Patterns

Figure 1 shows representative LISA cluster maps for the evening peak period (16:00-19:00), when congestion is most severe. Across all cities, spatial clustering is evident: congestion hotspots (HH) and coldspots (LL) form coherent spatial regions rather than random dispersions.

**Jakarta** exhibits the most complex pattern, with multiple disconnected hotspot clusters distributed across the metropolitan area. The highest intensity hotspots appear in central business districts and major arterial bottlenecks. Approximately 16.5% of segments experienced at least one hotspot designation across the 8 periods, but only 0% remained consistently classified as HH across all periods—indicating high temporal volatility.

**Bandung** shows more concentrated hotspot regions, particularly around university districts and commercial centers. The mountainous terrain constrains the road network, creating persistent bottlenecks at key corridors. Here, 14.5% of segments ever became hotspots.

**Semarang**, the smallest city, displays the most persistent spatial patterns. Hotspots concentrate along coastal arterials and the central business district, with 9.2% of segments entering HH state. The lower percentage reflects less severe congestion overall, but those hotspots that do form are more stable.

### 4.2 Classic Markov Transition Probabilities

Table 1 presents the 5×5 transition matrices for each city. The matrices exhibit strong diagonal dominance: most segments remain in their current LISA category from one period to the next. This temporal inertia is expected—traffic conditions evolve gradually within a day rather than exhibiting abrupt state changes.

**Table 1: Transition Probability Matrices (From rows to columns)**

*Jakarta:*
| From/To | NS | HH | LL | LH | HL |
|---------|-----|-----|-----|-----|-----|
| NS | **90.4%** | 2.4% | 2.5% | 2.5% | 2.3% |
| HH | 87.9% | **6.5%** | 0.4% | 4.2% | 1.0% |
| LL | 88.1% | 0.4% | **6.1%** | 0.8% | 4.7% |
| LH | 87.0% | 5.1% | 0.7% | **6.4%** | 0.8% |
| HL | 88.7% | 0.9% | 4.0% | 0.6% | **5.8%** |

*Bandung:*
| From/To | NS | HH | LL | LH | HL |
|---------|-----|-----|-----|-----|-----|
| NS | **90.8%** | 2.1% | 2.6% | 2.3% | 2.1% |
| HH | 79.4% | **12.0%** | 0.4% | 8.2% | 0.0% |
| LL | 81.9% | 0.2% | **10.9%** | 0.5% | 6.5% |
| LH | 76.3% | 9.8% | 0.2% | **13.7%** | 0.0% |
| HL | 78.3% | 0.4% | 6.2% | 1.0% | **14.1%** |

*Semarang:*
| From/To | NS | HH | LL | LH | HL |
|---------|-----|-----|-----|-----|-----|
| NS | **93.6%** | 1.3% | 1.5% | 1.7% | 1.9% |
| HH | 78.9% | **18.8%** | 0.0% | 2.3% | 0.0% |
| LL | 66.1% | 0.0% | **25.1%** | 0.0% | 8.7% |
| LH | 75.3% | 5.3% | 0.0% | **19.3%** | 0.0% |
| HL | 70.6% | 0.0% | 9.1% | 0.0% | **20.3%** |

**Key Observations:**

1. **Persistence Gradient**: Diagonal probabilities (boldface) increase from Jakarta → Bandung → Semarang for cluster states (HH, LL, LH, HL). Semarang's P(HH→HH) = 18.8% is nearly 3× higher than Jakarta's 6.5%.

2. **Regression to NS**: All cluster states show high probability of transitioning back to NS (not significant). This reflects the temporal nature of congestion: hotspots form during peak hours but dissipate during off-peak periods.

3. **Asymmetric Transitions**: Hotspots (HH) in Bandung have a notable transition probability to LH (8.2%), suggesting that as peak periods wane, segments transition from high-among-high to low-among-high—their own congestion clears while neighbors remain congested.

### 4.3 Hotspot Persistence Analysis

Figure 2 compares diagonal dominance (persistence probabilities) across cities. We focus on three key states:

| City | P(NS→NS) | P(HH→HH) | P(LL→LL) |
|------|----------|----------|----------|
| Jakarta | 90.4% | 6.5% | 6.1% |
| Bandung | 90.8% | 12.0% | 10.9% |
| Semarang | 93.6% | 18.8% | 25.1% |

**Interpretation**: The inverse relationship between city size and cluster persistence suggests that larger, more complex networks exhibit greater congestion volatility. Jakarta's hotspots are short-lived, potentially due to:
- More alternative routes enabling traffic redistribution
- Dynamic driver behavior responding to real-time information
- Greater heterogeneity in trip purposes and timing

Conversely, Semarang's high persistence (P(LL→LL) = 25.1%) indicates structural constraints: certain segments remain chronically uncongested (e.g., peripheral roads), while hotspots, once formed, are harder to dissolve due to limited network redundancy.

### 4.4 Steady-State Distributions

All three cities converge to similar long-run equilibrium distributions (Table 2):

**Table 2: Steady-State Distributions**

| State | Jakarta | Bandung | Semarang |
|-------|---------|---------|----------|
| NS | 90.1% | 89.6% | 91.9% |
| HH | 2.5% | 2.5% | 1.6% |
| LL | 2.5% | 2.8% | 2.1% |
| LH | 2.5% | 2.7% | 1.9% |
| HL | 2.4% | 2.4% | 2.5% |

Despite different transition dynamics, all cities stabilize at approximately 90% NS and 2-3% in each cluster category. This suggests a universal constraint: only a small fraction of road segments (~10%) exhibit statistically significant spatial autocorrelation at any given time, regardless of network size.

### 4.5 Spatial Contagion Evidence

Table 3 presents chi-squared test results for spatial homogeneity. The null hypothesis (H₀) is that transition probabilities are independent of neighbors' LISA states.

**Table 3: Spatial Contagion Tests**

| City | Max χ² | p-value | Degrees of Freedom | Conclusion |
|------|--------|---------|-------------------|------------|
| Jakarta | 2.54 | 0.111 | 1 | Fail to reject H₀ (weak evidence) |
| Bandung | 8.43 | **0.004** | 1 | **Reject H₀ (strong evidence)** |
| Semarang | 6.48 | **0.011** | 1 | **Reject H₀ (moderate evidence)** |

**Interpretation**: 

- **Bandung** (χ² = 8.43, p = 0.004) exhibits the strongest spatial contagion effect. When neighboring segments are in hotspot states, the focal segment's transition probabilities differ significantly from the unconditional probabilities. This implies that congestion spreads along corridors, consistent with Bandung's constrained network topology.

- **Semarang** (χ² = 6.48, p = 0.011) shows moderate spatial dependence, suggesting local diffusion of congestion—a segment adjacent to a hotspot is more likely to become congested than a segment in an uncongested area.

- **Jakarta** (χ² = 2.54, p = 0.111) shows only weak evidence of spatial contagion. The dense, highly connected network may enable congestion to dissipate more readily, reducing spatial spillover effects. Alternatively, heterogeneous traffic management (e.g., signal coordination, odd-even plate restrictions) may disrupt spatial contagion.

### 4.6 Temporal Persistence Statistics

Beyond Markov transitions, we computed additional persistence metrics:

**Table 4: Segment-Level Persistence**

| City | Category | Ever (%) | Always (%) | Avg Periods |
|------|----------|----------|------------|-------------|
| Jakarta | HH | 16.5 | 0.0 | 1.2 |
| | LL | 16.6 | 0.0 | 1.2 |
| | NS | 100.0 | 46.0 | 7.2 |
| Bandung | HH | 14.5 | 0.0 | 1.3 |
| | LL | 16.2 | 0.0 | 1.4 |
| | NS | 99.9 | 50.6 | 7.2 |
| Semarang | HH | 9.2 | 0.0 | 1.4 |
| | LL | 11.6 | 0.0 | 1.6 |
| | NS | 99.8 | 62.0 | 7.3 |

**Findings:**
- No segment remained in HH or LL for all 8 periods across any city, confirming that congestion is temporally dynamic.
- Average duration of hotspot designations increases with smaller city size: 1.2 periods (Jakarta) vs 1.4 periods (Semarang).
- Semarang has the highest percentage of perpetually NS segments (62%), indicating a more stable, less congested network overall.

---

## 5. Discussion

### 5.1 Implications for Urban Traffic Management

Our findings have several policy implications:

**1. City-Specific Strategies**: The inverse relationship between city size and hotspot persistence suggests that one-size-fits-all traffic management policies may be ineffective. Smaller cities like Semarang, with persistent hotspots, would benefit from structural interventions (e.g., capacity expansion, intersection redesign) targeting chronic bottlenecks. In contrast, Jakarta's volatile hotspots call for dynamic management strategies—adaptive signal control, real-time route guidance, and demand-responsive transit.

**2. Spatial Contagion and Corridor Management**: Evidence of spatial contagion in Bandung and Semarang indicates that congestion mitigation should adopt a corridor perspective rather than treating segments in isolation. Alleviating congestion at one bottleneck may reduce downstream impacts through spatial spillover effects. Conversely, introducing capacity constraints (e.g., lane reductions for bike infrastructure) could trigger cascading congestion to adjacent segments, necessitating corridor-level impact assessment.

**3. Temporal Targeting**: The strong regression to NS states (even from HH) suggests that many hotspots are peak-hour specific. Time-of-day pricing, congestion charging, or flexible work hours could shift demand away from peak periods, reducing hotspot frequency rather than requiring infrastructure expansion.

### 5.2 Methodological Contributions

**LISA Markov Framework**: While LISA has been widely used for static hotspot detection and Markov chains for temporal dynamics, the integration via Spatial Markov analysis remains underutilized in transportation research. Our workflow demonstrates that this combination reveals insights unobtainable from either method alone:
- LISA alone identifies where hotspots occur but not their temporal stability
- Markov alone captures transitions but ignores spatial structure
- Spatial Markov tests whether spatial context influences dynamics

**Scalability**: Our analysis handles 18,694 segments across 8 time periods efficiently using PySAL. Computation time for LISA analysis (all cities, all periods) was ~15 minutes on a standard laptop (Apple M1), demonstrating feasibility for operational use.

**Reproducibility**: By using exclusively open-source tools and providing complete code, we enable replication and adaptation. Practitioners can apply the same workflow to other cities by replacing input GeoPackages—no proprietary software licenses required.

### 5.3 Role of FOSS4G Tools

The PySAL ecosystem proved robust and well-suited for this analysis:

**Strengths:**
- **Modular design**: Separating spatial weights (libpysal), ESDA (esda), and dynamics (giddy) enables focused, maintainable code
- **Statistical rigor**: Permutation-based significance testing and chi-squared tests provide sound inferential frameworks
- **Integration**: Seamless interoperability with GeoPandas, NumPy, and Matplotlib reduces friction
- **Documentation**: Comprehensive API documentation and tutorials lower the learning curve

**Areas for Improvement:**
- **Visualization**: Built-in LISA plotting functions exist but are limited; most visualizations required custom Matplotlib code
- **Performance**: Permutation tests for large datasets (14k+ segments) can be slow; parallelization support would help
- **Spatial Markov interpretation**: The chi-squared test provides omnibus significance but not granular details on which lag-conditioned matrices drive the effect

**Comparison to Proprietary Tools**: Software like ArcGIS provides LISA via the "Cluster and Outlier Analysis" tool, but Spatial Markov analysis is absent. Proprietary tools also lack the scripting flexibility for batch processing across multiple cities and periods. The cost barrier (thousands of dollars for licenses) is prohibitive for many developing-world institutions.

**Reproducibility and Extensibility**: Our `traffic-congestion-pipeline` package (available on PyPI) encapsulates the entire workflow in a reusable, well-documented codebase. Researchers can install the package with a single command and reproduce our analysis or apply it to their own cities. This level of reproducibility is difficult to achieve with proprietary GUI-based tools, which often require manual point-and-click workflows that are hard to document and replicate.

### 5.4 Limitations

**1. Data Resolution**: Our analysis aggregates data into 8 daily periods. Finer temporal resolution (e.g., 15-minute intervals) might reveal different transition dynamics, particularly during peak-to-off-peak transitions.

**2. Spatial Weights**: We use KNN (k=8) uniformly across all cities. Network-based weights (e.g., neighbors along connected routes) might better capture congestion propagation, but constructing such weights requires detailed network topology.

**3. First-Order Markov Assumption**: We assume transitions depend only on the current state, ignoring longer memory effects. Higher-order Markov chains could test whether sequences like NS→HH→HH→NS have different dynamics than standalone transitions.

**4. Stationarity**: We pool transitions across all period pairs (7 transitions per segment). If transitions differ systematically between morning and evening peaks, the pooled matrix may obscure period-specific dynamics.

**5. Causality**: Spatial Markov tests for spatial dependence but does not establish causation. Significant contagion could reflect: (a) actual traffic propagation, (b) common exogenous factors (e.g., all segments affected by a stadium event), or (c) spatial autocorrelation in network design.

### 5.5 Future Directions

**1. Explanatory Variables**: Integrate land use, demographics, and event data to explain why certain segments become persistent hotspots. Spatial regression (e.g., using PySAL's `spreg`) could model jam_factor as a function of predictors like population density, commercial activity, and transit accessibility.

**2. Network Topology Metrics**: Incorporate centrality measures (betweenness, closeness) to test whether high-centrality segments exhibit different persistence patterns—are network hubs more or less resilient to congestion?

**3. Intervention Analysis**: If policy changes (e.g., new transit lines, road expansions) occur, difference-in-differences or synthetic control methods could assess impacts on transition probabilities.

**4. Real-Time Application**: Deploy the LISA Markov framework in near-real-time to detect emerging hotspots and predict short-term congestion evolution, feeding into traffic management center dashboards.

**5. Multi-City Meta-Analysis**: Expand the study to more cities across different countries to test generalizability of the persistence-size relationship and identify universal principles of urban congestion dynamics.

---

## 6. Conclusion

This study demonstrates the effectiveness of open-source geospatial tools for analyzing spatiotemporal traffic congestion dynamics in Indonesian cities. Using the PySAL ecosystem (esda, libpysal, giddy), we applied LISA Markov analysis to 264 million traffic observations across Jakarta, Bandung, and Semarang.

Our key findings are:

1. **Hotspot persistence is inversely related to city size**: Smaller cities (Semarang) exhibit higher temporal stability of congestion hotspots (P(HH→HH) = 18.8%) compared to larger cities (Jakarta: 6.5%), suggesting that network complexity and alternative route availability influence volatility.

2. **Spatial contagion varies by city**: Bandung (χ² = 8.43, p < 0.01) and Semarang (χ² = 6.48, p = 0.01) show statistically significant evidence that transition probabilities depend on neighbors' states, indicating congestion spreads locally. Jakarta shows weaker evidence, possibly due to network density and active traffic management.

3. **Temporal dynamics matter**: All cities show strong regression to non-significant states, confirming that congestion is temporally localized to peak periods rather than chronic. This has implications for demand management versus infrastructure expansion.

From a methodological standpoint, we showcase a complete, reproducible workflow using exclusively open-source tools. The PySAL ecosystem provides the statistical rigor, computational efficiency, and extensibility needed for operational traffic analysis, removing cost barriers that limit adoption in developing countries. By releasing our workflow as the `traffic-congestion-pipeline` Python package on PyPI, we enable researchers worldwide to replicate our analysis, apply it to their own cities, or extend it with new features—all without licensing costs or proprietary dependencies.

**Practical Recommendations:**
- Urban planners should prioritize corridor-level congestion analysis to account for spatial spillovers
- Smaller cities benefit more from targeted infrastructure improvements at persistent hotspots
- Larger cities require dynamic, adaptive traffic management to address volatile congestion patterns
- Open-source geospatial tools are mature enough for production use in transportation planning

**Broader Impact:** As cities worldwide grapple with congestion challenges, accessible analytical methods are essential. This work contributes to the FOSS4G mission by demonstrating that advanced spatial statistics can be performed without proprietary software, democratizing traffic analysis capabilities. The availability of our analysis pipeline as an open-source PyPI package further lowers barriers to adoption, enabling transportation agencies and researchers in resource-constrained settings to conduct sophisticated spatiotemporal analyses.

Future work will extend this framework to real-time prediction, incorporate explanatory variables through spatial regression, and conduct comparative studies across more cities to build generalizable theories of urban congestion dynamics.

---

## Acknowledgments

Traffic data were collected using HERE Technologies Traffic API. The analysis was conducted using open-source software: PySAL (v2.8+), GeoPandas (v0.14+), and Python (v3.11). We thank the PySAL development team for maintaining this invaluable scientific infrastructure. The complete analysis workflow has been packaged and released as `traffic-congestion-pipeline` on PyPI to facilitate reproducibility and community contributions.

## Author Contributions

**Firman Hadi**: Conceptualization, Methodology, Software, Data Collection, Formal Analysis, Writing - Original Draft, Visualization, Project Administration

**Fauzan Abdullah**: Methodology, Formal Analysis (Statistical Methods), Validation, Writing - Review & Editing

**Yasser Wahyuddin**: Data Curation, Software, Validation, Writing - Review & Editing

**L.M. Sabri**: Resources, Supervision, Writing - Review & Editing, Project Administration

All authors have read and agreed to the published version of the manuscript.

## Conflict of Interest

The authors declare no conflict of interest.

## Funding

This research received no external funding.

## Data Availability

**Code and Software:**
- Analysis pipeline: `pip install traffic-congestion-pipeline` (PyPI: https://pypi.org/project/traffic-congestion-pipeline/)
- GitHub repository: https://github.com/firmanhadi21/traffic-analyses
- Documentation: https://firmanhadi21.github.io/traffic-analyses

**Data:**
Traffic data from HERE Technologies are subject to commercial licensing and cannot be redistributed. Researchers can obtain similar data through:
- HERE Technologies Academic Program
- Alternative providers (TomTom, Google Maps Platform)
- OpenStreetMap-based traffic simulators (SUMO)

Our pipeline supports multiple data providers, enabling researchers to use publicly available alternatives while following the same analytical workflow.

---

## References

Anselin, L. (1995). Local indicators of spatial association—LISA. *Geographical Analysis*, 27(2), 93-115.

Baker, W. L. (1989). A review of models of landscape change. *Landscape Ecology*, 2(2), 111-133.

Batty, M. (1976). Urban modelling: Algorithms, calibrations, predictions. Cambridge University Press.

Chegut, A., Eichholtz, P., & Kok, N. (2015). The price dynamics of green housing: A housing market perspective on sustainability. In *The sustainable urban development reader* (pp. 315-322). Routledge.

Cheng, Q., Liu, Z., Lin, Y., & Zhou, X. S. (2012). An s-shaped three-parameter (S3) traffic stream model with consistent car following relationship. *Transportation Research Part B*, 53, 127-142.

Jordahl, K., Van den Bossche, J., Fleischmann, M., Wasserman, J., McBride, J., Gerard, J., ... & Leblanc, F. (2020). geopandas/geopandas: v0.8.1. *Zenodo*.

Li, Y., Canepa, E. S., & Claudel, C. G. (2015). Optimal traffic control in highway transportation networks using Markov chain modeling. *Transportation Research Part C*, 63, 66-81.

Min, W., & Wynter, L. (2011). Real-time road traffic prediction with spatio-temporal correlations. *Transportation Research Part C*, 19(4), 606-616.

Moran, P. A. (1950). Notes on continuous stochastic phenomena. *Biometrika*, 37(1/2), 17-23.

Prasannakumar, V., Vijith, H., Charutha, R., & Geetha, N. (2011). Spatio-temporal clustering of road accidents: GIS based analysis and assessment. *Procedia-Social and Behavioral Sciences*, 21, 317-325.

Rey, S. J. (2001). Spatial empirics for economic growth and convergence. *Geographical Analysis*, 33(3), 195-214.

Rey, S. J., & Anselin, L. (2007). PySAL: A Python library of spatial analytical methods. *The Review of Regional Studies*, 37(1), 5-27.

Rey, S. J., Arribas-Bel, D., & Wolf, L. J. (2021). *Geographic Data Science with Python*. CRC Press.

Tobler, W. R. (1970). A computer movie simulating urban growth in the Detroit region. *Economic Geography*, 46(sup1), 234-240.

Wang, C., Quddus, M. A., & Ison, S. G. (2013). The effect of traffic and road characteristics on road safety: A review and future research direction. *Safety Science*, 57, 264-275.

World Bank. (2020). *Indonesia Economic Quarterly: Investing in Opportunity*. World Bank Group.

Zhang, X., Lin, H., & Huang, W. (2011). Road traffic accident analysis using spatial autocorrelation. *International Conference on Remote Sensing, Environment and Transportation Engineering*, 2482-2485.

Zheng, H. W., Shen, G. Q., Wang, H., & Hong, J. (2013). Simulating land use change in urban renewal areas: A case study in Hong Kong. *Habitat International*, 46, 23-34.

---

**END OF PAPER**

*Submitted to FOSS4G 2026 - Academic Track*  
*Hiroshima, Japan*  
*Word Count: ~7,500 (excluding references and tables)*
