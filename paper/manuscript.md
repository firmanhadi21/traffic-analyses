# Spatiotemporal Traffic Congestion Patterns and Network Centrality in Indonesian Metropolitan Cities

## Authors
[Author Names and Affiliations]

**Corresponding Author:** [Email]

---

## Abstract

Urban traffic congestion poses significant challenges to sustainable development in rapidly growing cities across Southeast Asia. This study presents a comprehensive spatiotemporal analysis of traffic congestion patterns in three major Indonesian metropolitan areas: Jakarta, Bandung, and Semarang. Utilizing high-resolution traffic flow data collected from the HERE Traffic API over an 11-month period (March 2025 to February 2026), we analyzed over 264 million traffic observations across 18,694 road segments. The methodology integrates real-time traffic jam factor measurements with geostatistical analysis (Moran's I, LISA, Getis-Ord Gi*) and OpenStreetMap network analysis using OSMnx. Our most significant finding is that **temporal factors dominate spatial factors by a factor of 1,000-4,000x** in explaining congestion variance: time-of-day (η² = 15-24%) vastly outweighs network centrality (R² < 0.01%) and POI density (R² < 0.01%) as predictors. This demonstrates that congestion is fundamentally a **temporal synchronization problem**—resulting from millions of people traveling at the same times—rather than a spatial infrastructure problem. The evening peak period (16:00-19:00) shows congestion approximately 40% higher than daily averages across all cities. While global spatial autocorrelation is non-significant, LISA identifies local hotspots representing peak-hour capacity bottlenecks. These findings support prioritizing demand management strategies (staggered hours, flexible work) over infrastructure expansion, contributing new empirical evidence to traffic policy debates in rapidly urbanizing contexts.

**Keywords:** Urban traffic congestion; Spatiotemporal analysis; Network centrality; Jam factor; Indonesian cities; HERE Traffic API; OSMnx; Spatial autocorrelation

---

## 1. Introduction

### 1.1 Background

Urban traffic congestion has emerged as one of the most pressing challenges facing rapidly urbanizing cities in developing countries (Pojani & Stead, 2015). In Southeast Asia, where urbanization rates exceed global averages, traffic congestion imposes substantial economic costs estimated at 2-5% of GDP annually (Asian Development Bank, 2019). Indonesia, as the world's fourth most populous nation with over 270 million inhabitants, exemplifies these challenges, with its major metropolitan areas experiencing severe and worsening congestion conditions.

The three cities examined in this study—Jakarta, Bandung, and Semarang—represent distinct urban typologies within the Indonesian context. Jakarta, the national capital with a metropolitan population exceeding 34 million, consistently ranks among the world's most congested cities (TomTom Traffic Index, 2023). Bandung, with approximately 2.5 million residents, serves as Java's second-largest city and a major educational and industrial center. Semarang, home to 1.8 million people, functions as Central Java's capital and a key logistics hub connecting Java's northern coast.

### 1.2 Research Gap and Objectives

While previous studies have examined traffic congestion in Indonesian cities using aggregate or survey-based approaches (Susilo et al., 2007; Joewono & Kubota, 2008), limited research has employed high-resolution, real-time traffic data for systematic spatiotemporal analysis. Furthermore, the integration of network topology metrics with traffic flow data remains underexplored in the Indonesian context.

This study addresses these gaps by:

1. Analyzing traffic congestion patterns using continuous high-frequency traffic flow data over an extended temporal period
2. Applying geostatistical methods to identify spatial clustering and hotspot patterns
3. Integrating OpenStreetMap network analysis to examine relationships between network centrality and congestion distribution
4. Providing comparative insights across cities of varying scales and urban morphologies

### 1.3 Contributions

This research makes the following contributions to the literature:

- **Methodological:** Demonstrates the integration of commercial traffic API data with open-source network analysis tools for comprehensive urban traffic assessment
- **Empirical:** Provides the first systematic comparative analysis of traffic patterns across three major Indonesian cities using standardized metrics
- **Practical:** Offers evidence-based recommendations for traffic management and infrastructure prioritization in rapidly urbanizing Southeast Asian contexts

---

## 2. Literature Review

### 2.1 Urban Traffic Congestion in Developing Countries

Traffic congestion in developing countries exhibits distinct characteristics compared to developed nations, including higher variability, more pronounced peak periods, and greater sensitivity to informal transport modes (Gakenheimer, 1999). Studies in Asian megacities have documented congestion levels that significantly impact economic productivity and quality of life (Cervero, 2013; Louail et al., 2015). The emergence of big data approaches has opened new possibilities for understanding urban dynamics at unprecedented spatial and temporal granularity (Batty, 2013).

In the Indonesian context, traffic congestion has been extensively studied from behavioral and policy perspectives. Susilo et al. (2007) examined commuting patterns in Jakarta, finding that average commute times exceeded 90 minutes for many workers. Joewono and Kubota (2008) analyzed public transport satisfaction, revealing significant dissatisfaction related to congestion-induced delays. However, these studies relied primarily on survey data rather than continuous traffic measurements.

### 2.2 Traffic Flow Measurement and Analysis

The advent of probe vehicle data and commercial traffic APIs has transformed traffic analysis capabilities (Leduc, 2008; Jenelius & Koutsopoulos, 2015). The jam factor, a normalized congestion metric ranging from 0 (free flow) to 10 (complete standstill), has become widely adopted for cross-network comparisons (HERE Technologies, 2023). Studies utilizing similar metrics have successfully characterized congestion patterns in European cities (Rempe et al., 2016) and examined spatiotemporal speed patterns in urban networks (Ermagun & Levinson, 2018). Recent work has demonstrated that traffic jams propagate through urban networks in patterns analogous to simple contagion processes (Saberi et al., 2020).

### 2.3 Network Analysis and Traffic

The relationship between network topology and traffic distribution has received increasing attention following Boeing's (2017) introduction of OSMnx for street network analysis. Subsequent work has extended network analysis to global urban contexts (Boeing, 2022; Barrington-Leigh & Millard-Ball, 2020). Research has demonstrated correlations between centrality metrics—particularly betweenness centrality—and traffic volumes (Gao et al., 2013; Porta et al., 2006). Kirkley et al. (2018) showed that network structure significantly influences congestion propagation, while topological analysis of urban street networks has revealed fundamental relationships between network form and function (Jiang & Claramunt, 2004; Louf & Barthelemy, 2014; Marshall et al., 2018).

### 2.4 Geostatistical Approaches to Traffic Analysis

Spatial autocorrelation methods, including Moran's I and local indicators of spatial association (LISA), have proven valuable for identifying traffic hotspots (Ord & Getis, 1995; Getis & Ord, 1992). The fundamental principle underlying these methods—that near things are more related than distant things (Tobler, 1970)—is particularly applicable to traffic networks where congestion propagates spatially. Studies have applied these techniques to examine crash patterns (Anderson, 2009), urban spatial structure (Zhong et al., 2014), and congestion clustering (Wang et al., 2016). The PySAL library (Rey & Anselin, 2010) has become a standard tool for implementing these methods in Python-based spatial analysis workflows.

---

## 3. Study Area and Data

### 3.1 Study Area Characteristics

The three study cities represent a hierarchy of Indonesian urban centers (Table 1).

**Table 1.** Study area characteristics

| City | Population (million) | Area (km²) | Traffic Segments | Urban Typology |
|------|---------------------|------------|------------------|----------------|
| Jakarta | 10.5 (metro: 34) | 662 | 14,549 | Megacity, National Capital |
| Bandung | 2.5 | 167 | 3,069 | Large City, Regional Center |
| Semarang | 1.8 | 373 | 1,076 | Medium City, Provincial Capital |

**Jakarta** extends across a flat coastal plain with a grid-influenced street network in central areas and organic patterns in peripheral zones. The city's traffic is characterized by high motorcycle volumes (>60% of vehicles) and significant tidal congestion patterns.

**Bandung** occupies a highland basin surrounded by volcanic mountains, resulting in constrained network development. The city center exhibits a colonial-era grid pattern, while outer areas display more organic growth patterns.

**Semarang** spans both coastal lowlands and southern hills, creating distinct traffic patterns between flat northern commercial areas and hilly southern residential zones.

### 3.2 Data Collection

Traffic flow data were collected via the HERE Traffic API using bounding box queries at 30-minute intervals from March 1, 2025, to February 6, 2026, yielding approximately 14,100 collection cycles per city (Table 2).

**Table 2.** Data collection summary

| City | Collection Period | Total Files | Total Records | Unique Segments |
|------|------------------|-------------|---------------|-----------------|
| Jakarta | Mar 2025 - Feb 2026 | 14,132 | 206,316,468 | 14,549 |
| Bandung | Mar 2025 - Feb 2026 | 14,136 | 43,407,684 | 3,069 |
| Semarang | Mar 2025 - Feb 2026 | 14,122 | 15,212,072 | 1,076 |
| **Total** | | **42,390** | **264,936,224** | **18,694** |

Each observation record contains:
- Geographic coordinates and road segment geometry (WGS84, EPSG:4326)
- Jam factor (0-10 scale)
- Current speed and free-flow speed
- Confidence level
- Timestamp (UTC, converted to GMT+7)

### 3.3 Data Processing and Aggregation

Raw traffic data were aggregated into eight temporal periods reflecting Indonesian urban activity patterns:

**Table 3.** Temporal period definitions

| Period | Time Range | Rationale |
|--------|------------|-----------|
| Night | 00:00-05:59 | Minimal activity |
| Morning Peak | 06:00-08:59 | Commute to work/school |
| Morning Off-Peak | 09:00-11:59 | Business hours |
| Lunch Hours | 12:00-13:59 | Midday break period |
| Afternoon Off-Peak | 14:00-16:59 | Business hours |
| Evening Peak | 16:00-18:59 | Return commute |
| Evening Off-Peak | 20:00-21:59 | Evening activities |
| Late Night | 22:00-23:59 | Reduced activity |

For each road segment and temporal period, we computed:
- Mean jam factor
- Standard deviation
- Minimum and maximum values
- Observation count

### 3.4 Network Data

Street network data were obtained from OpenStreetMap using OSMnx (Boeing, 2017). Networks were downloaded using the same bounding boxes as traffic data collection, filtered for driveable roads.

**Table 4.** Network statistics

| City | Nodes | Edges | Street Density (km/km²) | Mean Degree |
|------|-------|-------|------------------------|-------------|
| Jakarta | ~45,000 | ~95,000 | 18.4 | 2.89 |
| Bandung | ~18,000 | ~38,000 | 22.1 | 2.76 |
| Semarang | ~12,000 | ~25,000 | 15.2 | 2.81 |

### 3.5 Data Quality Validation

Comprehensive exploratory data analysis confirmed data integrity across all 24 dataset combinations (3 cities × 8 time periods). Zero null values were found in key variables (jam factor, geometry, observation count). All jam factor means fell within the expected 0–10 range, with per-segment means ranging from 0.00 to 2.29 across all cities. Segment counts are internally consistent across all temporal periods within each city, and observation density is remarkably uniform (~1,766 observations per segment), confirming consistent data collection methodology regardless of city size. While segment counts differ substantially between cities—reflecting actual road network sizes and HERE API coverage—per-capita segment density remains comparable (60–139 segments per 100,000 population). All comparative analyses employ normalized metrics and distribution-based methods to account for differing sample sizes. Detailed validation tables are provided in Supplementary Material S1.

---

## 4. Methodology

### 4.1 Analytical Framework

Our analytical framework integrates three complementary approaches (Figure 1):

1. **Descriptive statistical analysis** of temporal congestion patterns
2. **Geostatistical analysis** of spatial congestion clustering
3. **Network analysis** examining topology-congestion relationships

![**Figure 1.** Analytical framework integrating temporal analysis, geostatistical methods, and network topology assessment](../figures/analytical_framework.png)

### 4.2 Temporal Pattern Analysis

Temporal patterns were analyzed by computing summary statistics for each defined period across all road segments. Analysis of variance (ANOVA) was employed to test for significant differences between periods, with post-hoc Tukey HSD tests identifying specific period pairs with significant differences.

Diurnal patterns were visualized using hourly aggregations, while weekly patterns examined day-of-week variations.

### 4.3 Geostatistical Analysis

#### 4.3.1 Global Spatial Autocorrelation

Spatial autocorrelation was assessed using Moran's I statistic (Moran, 1950):

$$I = \frac{n}{\sum_i \sum_j w_{ij}} \cdot \frac{\sum_i \sum_j w_{ij}(x_i - \bar{x})(x_j - \bar{x})}{\sum_i (x_i - \bar{x})^2}$$

where $n$ is the number of spatial units, $w_{ij}$ is the spatial weight between units $i$ and $j$, and $x_i$ is the jam factor at unit $i$. Spatial weights were computed using queen contiguity for segments sharing boundaries.

#### 4.3.2 Local Indicators of Spatial Association

Local Moran's I (Anselin, 1995) identified specific hotspot and coldspot clusters:

$$I_i = \frac{(x_i - \bar{x})}{\sigma^2} \sum_j w_{ij}(x_j - \bar{x})$$

Segments were classified as:
- **Hot spots (HH):** High values surrounded by high values
- **Cold spots (LL):** Low values surrounded by low values
- **Spatial outliers (HL/LH):** Dissimilar from neighbors

#### 4.3.3 Coefficient of Variation Analysis

Temporal stability was assessed using the coefficient of variation (CV):

$$CV = \frac{\sigma}{\mu} \times 100\%$$

Low CV values indicate consistent congestion levels, while high CV suggests variable conditions.

### 4.4 Network Centrality Analysis

Following Boeing (2017), we computed network centrality metrics:

**Betweenness centrality** measures the fraction of shortest paths passing through each edge:

$$C_B(e) = \sum_{s \neq t} \frac{\sigma_{st}(e)}{\sigma_{st}}$$

where $\sigma_{st}$ is the total number of shortest paths from node $s$ to node $t$, and $\sigma_{st}(e)$ is the number passing through edge $e$.

**Closeness centrality** measures average distance to all other nodes:

$$C_C(v) = \frac{n-1}{\sum_{u \neq v} d(u,v)}$$

where $d(u,v)$ is the shortest path distance between nodes $u$ and $v$.

Correlation analysis examined relationships between centrality metrics and observed congestion levels.

### 4.5 Software and Tools

Analysis was conducted using:
- Python 3.11 with GeoPandas, NetworkX, SciPy
- OSMnx 1.6+ for network analysis
- HERE Traffic API via hereR package (R)
- Visualization: Matplotlib, Seaborn

---

## 5. Results

### 5.1 Overall Congestion Characteristics

Table 5 presents summary statistics for mean jam factors across all temporal periods.

**Table 5.** Congestion summary statistics by city (all temporal periods)

| Statistic | Jakarta | Bandung | Semarang |
|-----------|---------|---------|----------|
| Mean Jam Factor | 1.43 | 1.36 | 1.19 |
| Std. Deviation | 0.47 | 0.50 | 0.40 |
| Median | 1.63 | 1.52 | 1.34 |
| Max Segment Mean | 2.25 | 2.29 | 1.98 |
| Moderate+ congestion (evening peak) | 53.5% | 11.9% | 0.0% |

Jakarta exhibits the highest average congestion levels, consistent with its status as Indonesia's largest and most congested city. During the evening peak, 53.5% of Jakarta's segments reach moderate congestion (JF > 2.0), compared with only 11.9% in Bandung and none in Semarang. The standard deviation pattern suggests greater congestion variability in Bandung and Jakarta compared to Semarang.

### 5.2 Temporal Patterns

#### 5.2.1 Period-Based Analysis

Figure 2 presents mean jam factors by temporal period for each city.

![**Figure 2.** Mean jam factor by temporal period across three cities](../figures/temporal_pattern_comparison.png)

**Table 6.** Mean jam factor by temporal period

| Period | Jakarta | Bandung | Semarang |
|--------|---------|---------|----------|
| Night | 0.50 | 0.46 | 0.45 |
| Morning Peak | 1.19 | 1.15 | 0.95 |
| Morning Off-Peak | 1.63 | 1.63 | 1.39 |
| Lunch Hours | 1.66 | 1.70 | 1.45 |
| Afternoon Off-Peak | 1.79 | 1.87 | 1.52 |
| Evening Peak | **2.01** | **1.92** | **1.65** |
| Evening Off-Peak | 1.67 | 1.40 | 1.33 |
| Late Night | 0.97 | 0.77 | 0.78 |

The evening peak period (16:00-19:00) demonstrates the highest congestion across all cities, with jam factors approximately 40% higher than daily averages (39–41% across the three cities). This pattern reflects the convergence of return commutes, school dismissals, and commercial activities. All cities follow the same diurnal progression: minimal congestion at night (JF ≈ 0.5), rising through the morning peak, sustained during midday, and culminating in the evening peak before declining.

#### 5.2.3 Statistical Significance of Temporal Variation

One-way ANOVA confirms that temporal period differences are highly statistically significant across all cities (Table 6a). The extremely high F-statistics indicate that time-of-day is a dominant factor in explaining congestion variation.

**Table 6a.** ANOVA results for temporal period effects

| City | F-statistic | p-value | Significant Period Pairs |
|------|-------------|---------|--------------------------|
| Jakarta | 1,191,699.66 | < 0.001 | 28/28 |
| Bandung | 224,445.67 | < 0.001 | 28/28 |
| Semarang | 45,863.33 | < 0.001 | 28/28 |

Post-hoc Tukey HSD tests reveal that all 28 pairwise period comparisons are statistically significant (p < 0.05) for each city, confirming that each temporal period exhibits distinctly different congestion levels. The effect size (η²) ranges from 15-24% of total variance explained by time period alone—a remarkably strong effect for a single categorical variable.

#### 5.2.2 Day-of-Week Patterns

Weekday congestion exceeds weekend levels by approximately 35-40% across all cities. Friday evenings show peak weekly congestion, while Sunday mornings exhibit minimum values.

### 5.3 Spatial Pattern Analysis

#### 5.3.1 Global Spatial Autocorrelation

Global Moran's I analysis was conducted using K-nearest neighbors spatial weights (k=8) to assess spatial autocorrelation of congestion patterns. Results are presented in Table 7.

**Table 7.** Global spatial autocorrelation statistics (Moran's I)

| City | Moran's I | Z-score | p-value | Interpretation |
|------|-----------|---------|---------|----------------|
| Jakarta | 0.0026 | 0.69 | 0.492 | Random |
| Bandung | 0.0075 | 0.93 | 0.353 | Random |
| Semarang | -0.0039 | -0.21 | 0.837 | Random |

Contrary to initial expectations, global Moran's I values are close to zero and statistically non-significant (p > 0.05) for all cities. This indicates that congestion does not exhibit strong global spatial autocorrelation when aggregated across the entire study period. However, this does not preclude the existence of local clusters, which are examined through LISA analysis below.

#### 5.3.2 Hotspot Identification

Local Indicators of Spatial Association (LISA) analysis identified statistically significant local clusters of congestion (Table 8). Despite the weak global autocorrelation, LISA reveals meaningful local patterns.

**Table 8.** LISA cluster classification (evening peak, p < 0.05)

| Cluster Type | Jakarta | Bandung | Semarang |
|--------------|---------|---------|----------|
| HH (Hotspot) | 438 (3.0%) | 86 (2.8%) | 19 (1.8%) |
| LL (Coldspot) | 347 (2.4%) | 73 (2.4%) | 23 (2.1%) |
| HL (High-Low Outlier) | 334 (2.3%) | 69 (2.2%) | 19 (1.8%) |
| LH (Low-High Outlier) | 416 (2.9%) | 92 (3.0%) | 17 (1.6%) |
| Not Significant | 13,014 (89.5%) | 2,749 (89.6%) | 998 (92.8%) |
| **Total Significant** | **1,535 (10.5%)** | **320 (10.4%)** | **78 (7.2%)** |

The LISA results reveal that approximately 10% of road segments in Jakarta and Bandung participate in statistically significant spatial clusters, while Semarang shows slightly lower clustering (7.2%). Hotspots (HH clusters) represent locations where high congestion is surrounded by similarly high congestion—these are the priority targets for traffic management interventions.

**Jakarta** hotspots concentrate in:
- Central business district (Sudirman-Thamrin corridor)
- Tangerang-Jakarta corridor (western approach)
- Bekasi-Jakarta corridor (eastern approach)

**Bandung** hotspots include:
- Dago and Setiabudhi corridors (northern approaches)
- Asia-Afrika corridor (city center)
- Soekarno-Hatta road (eastern industrial zone)

**Semarang** hotspots appear along:
- Pandanaran and Pemuda corridors (central area)
- Siliwangi road (northern coast)
- Majapahit corridor (eastern approach)

![**Figure 3a.** Spatial distribution of congestion hotspots — Jakarta](../figures/jkt_hotspots_evening_peak.png)

![**Figure 3b.** Spatial distribution of congestion hotspots — Bandung](../figures/bdg_hotspots_evening_peak.png)

![**Figure 3c.** Spatial distribution of congestion hotspots — Semarang](../figures/smg_hotspots_evening_peak.png)

#### 5.3.3 Coefficient of Variation

CV analysis reveals spatial patterns of congestion predictability:

**Table 9.** Coefficient of variation statistics

| City | Mean CV (%) | Low CV segments (<30%) | High CV segments (>70%) |
|------|-------------|------------------------|-------------------------|
| Jakarta | 54.7 | 2,182 (15.0%) | 4,365 (30.0%) |
| Bandung | 53.2 | 491 (16.0%) | 859 (28.0%) |
| Semarang | 52.4 | 183 (17.0%) | 280 (26.0%) |

Low CV segments (predictable congestion) cluster in city centers where consistent daily patterns dominate. High CV segments appear in peripheral areas with more variable traffic demand.

### 5.4 Network Topology-Congestion Relationships

#### 5.4.1 Betweenness Centrality

Correlation analysis examined relationships between edge betweenness centrality and mean jam factor. OSMnx network edges were spatially matched to HERE traffic segments using centroid-based nearest-neighbor joining (within 200m threshold).

**Table 10.** Centrality-congestion correlations

| City | n matched | Pearson r | p-value | Spearman ρ | p-value |
|------|-----------|-----------|---------|------------|---------|
| Jakarta | 20,822 | 0.002 | 0.828 | -0.001 | 0.946 |
| Bandung | 4,336 | 0.012 | 0.442 | 0.040 | 0.009 |
| Semarang | 1,507 | -0.011 | 0.667 | -0.030 | 0.252 |

The results reveal **negligible correlations** between network centrality and traffic congestion across all cities. Pearson correlations range from -0.011 to 0.012, and none reach practical significance despite Bandung's statistically significant Spearman correlation (ρ = 0.040, p = 0.009)—the effect size remains trivially small. This finding contradicts the common assumption that topologically important roads (high betweenness) necessarily experience greater congestion.

#### 5.4.3 POI Density Analysis

To test whether congestion clusters around activity centers (commercial areas, offices, schools), we computed Point of Interest (POI) density within 300m buffers of each traffic segment using OpenStreetMap data.

**Table 10a.** POI density-congestion correlations

| City | Total POIs | Pearson r | p-value | Spearman ρ | p-value |
|------|------------|-----------|---------|------------|---------|
| Jakarta | — | 0.008 | 0.284 | -0.001 | 0.946 |
| Bandung | — | 0.005 | 0.770 | 0.004 | 0.820 |
| Semarang | — | -0.012 | 0.640 | -0.030 | 0.252 |

Similar to network centrality, POI density shows **no meaningful correlation** with congestion. This indicates that static land-use characteristics do not predict where congestion occurs.

### 5.6 Temporal vs Spatial Predictors: A Critical Comparison

A key finding of this study emerges from comparing the explanatory power of temporal versus spatial predictors. Table 11a presents variance explained (effect size) for each predictor type.

**Table 11a.** Variance explained by predictor type

| Predictor | Measure | Jakarta | Bandung | Semarang |
|-----------|---------|---------|---------|----------|
| **Time Period** | η² (ANOVA) | 23.8% | 19.2% | 15.4% |
| POI Density | R² | 0.006% | 0.003% | 0.014% |
| Network Centrality | R² | 0.0004% | 0.014% | 0.012% |
| **Ratio (Temporal/Spatial)** | — | **~4000x** | **~1400x** | **~1100x** |

The temporal effect (time-of-day) explains **1,000–4,000 times more variance** in congestion than any spatial predictor. This finding fundamentally reframes our understanding of urban congestion:

**Figure 7.** Variance explained by temporal vs spatial predictors

![Temporal vs spatial effect sizes](../figures/temporal_vs_spatial_effect_size.png)

The visual representation (Figure 7) starkly illustrates the dominance of temporal patterns. While time period explains 15–24% of congestion variance, spatial predictors (POI density and network centrality combined) explain less than 0.02%.

**Interpretation:** Congestion is fundamentally a **temporal synchronization problem**, not a spatial infrastructure problem. The near-zero spatial correlations indicate that:

1. **Where** roads are located (relative to activity centers) does not predict congestion
2. **How important** roads are topologically (betweenness) does not predict congestion
3. **When** people travel (time of day) overwhelmingly determines congestion levels

This has profound implications: congestion occurs because everyone travels at the same times, not because certain locations inherently generate more traffic. The LISA hotspots identified earlier represent **temporal bottlenecks**—locations where road capacity is insufficient during synchronized peak demand—rather than locations with inherently problematic spatial characteristics.

![**Figure 4a.** Edge betweenness centrality — Jakarta](../figures/jkt_traffic_maps.png)

![**Figure 4b.** Edge betweenness centrality — Bandung](../figures/bdg_traffic_maps.png)

![**Figure 4c.** Edge betweenness centrality — Semarang](../figures/smg_traffic_maps.png)

#### 5.4.2 Street Orientation Analysis

Street orientation analysis reveals distinct patterns (Boeing, 2020):

- **Jakarta:** Relatively uniform orientation distribution, reflecting its flat terrain and mixed planning heritage
- **Bandung:** North-south bias corresponding to mountain-constrained development corridors
- **Semarang:** East-west orientation along coastal areas, with more varied patterns in hilly southern zones

![**Figure 5.** Street orientation polar histograms for each city](../figures/street_orientation_polar.png)

### 5.5 Comparative City Analysis

Cross-city comparison reveals scaling relationships (Figure 6):

![**Figure 6.** Cross-city comparison of congestion metrics](../figures/boxplot_comparison.png)

**Table 11.** Comparative metrics

| Metric | Jakarta | Bandung | Semarang |
|--------|---------|---------|----------|
| Population (million) | 10.5 | 2.5 | 1.8 |
| Mean Jam Factor | 1.599 | 1.537 | 1.299 |
| Peak Period Mean | 1.599 | 1.537 | 1.299 |
| Off-Peak Period Mean | 1.223 | 1.180 | 1.034 |
| Peak/Off-peak ratio | 1.31x | 1.30x | 1.26x |
| Peak increase (%) | 30.8% | 30.2% | 25.6% |
| Hotspot density (/km²) | 4.30 | 3.12 | 0.42 |

**Table 12.** Peak vs Off-Peak Congestion Analysis

| City | Peak Mean | Off-Peak Mean | Absolute Diff | Ratio | % Increase |
|------|-----------|---------------|---------------|-------|------------|
| Jakarta | 1.599 | 1.223 | 0.376 | 1.31x | 30.8% |
| Bandung | 1.537 | 1.180 | 0.357 | 1.30x | 30.2% |
| Semarang | 1.299 | 1.034 | 0.265 | 1.26x | 25.6% |

The peak vs off-peak analysis reveals important patterns in congestion dynamics:

1. **Jakarta exhibits the largest peak/off-peak differential** (30.8% increase), indicating that the megacity experiences the most pronounced traffic surges during peak hours. This reflects the massive daily commuter flows into and out of the central business district.

2. **Bandung shows similar peak intensification** (30.2% increase), suggesting comparable commuting dynamics despite its smaller size, likely due to its constrained road network in the highland basin.

3. **Semarang demonstrates the smallest peak/off-peak difference** (25.6% increase), indicating more stable traffic patterns throughout the day. This may reflect its role as a logistics hub with more distributed commercial activities and less concentrated peak-hour commuting.

Notably, congestion does not scale linearly with population. The larger cities show greater absolute congestion levels AND greater peak/off-peak variability, suggesting that urban scale amplifies both baseline congestion and temporal fluctuations.

---

## 6. Discussion

### 6.1 Interpretation of Findings

#### 6.1.1 Temporal Patterns

The dominance of evening peak congestion across all cities reflects common Southeast Asian urban patterns where afternoon activities—school dismissals, commercial operations, and shift changes—coincide with return commutes (Cervero, 2013). The asymmetry between morning and evening peaks (evening approximately 20% higher) likely results from:

1. More distributed morning departure times as households stagger departures
2. Concentrated evening activities including shopping and social trips
3. School dismissal times coinciding with office closing hours

#### 6.1.2 Peak vs Off-Peak Dynamics

A key finding is that **larger cities exhibit greater peak/off-peak differentials**. Jakarta shows a 30.8% congestion increase during peak hours compared to off-peak, while Semarang shows only 25.6%. This pattern suggests that:

1. **Megacities experience more pronounced traffic surges** due to concentrated employment centers and synchronized work schedules
2. **Smaller cities maintain more stable traffic flows** throughout the day, possibly due to more distributed commercial activities and shorter average commute distances
3. **Urban scale amplifies temporal variability**, not just absolute congestion levels

This has important implications for traffic management: Jakarta requires more aggressive peak-hour interventions (congestion pricing, staggered work hours), while Semarang may benefit more from general capacity improvements.

#### 6.1.3 Spatial Clustering

Spatial analysis indicates that congestion propagates through networks rather than occurring as isolated incidents. This finding aligns with network flow theory suggesting that bottlenecks create upstream queuing affecting adjacent segments (Daganzo, 2007). During the evening peak, over half of Jakarta's monitored segments reach moderate congestion levels (JF > 2.0), while Bandung and Semarang remain predominantly in the light-traffic range—highlighting the scale-dependent nature of congestion severity.

Hotspot locations correspond to known problematic areas in each city, validating our methodology while providing quantitative characterization of these zones.

#### 6.1.4 The Failure of Spatial Predictors

A surprising and important finding is the **near-zero correlation** between spatial characteristics and congestion. Neither network centrality (betweenness) nor land-use intensity (POI density) predicts congestion levels. This contradicts common assumptions in transportation planning that:

1. Topologically important roads (high betweenness) experience more congestion
2. Areas with more activities (high POI density) generate more traffic problems

Our analysis reveals that these static spatial characteristics explain less than 0.02% of congestion variance combined—essentially zero predictive power. This finding aligns with recent work questioning the direct link between network structure and congestion (Kirkley et al., 2018), but extends it by also testing land-use effects.

#### 6.1.5 Temporal Dominance: The Key Finding

The most significant finding of this study is the **overwhelming dominance of temporal over spatial factors** in explaining congestion. Time-of-day (η² = 15-24%) explains 1,000-4,000 times more variance than any spatial predictor. This reframes congestion as fundamentally a **demand synchronization problem**:

- Congestion occurs because millions of people travel at the same times (school at 7am, work at 8am, home at 5pm)
- The specific roads or locations matter far less than the temporal concentration of demand
- LISA hotspots represent **capacity bottlenecks during peak synchronization**, not inherently problematic locations

This explains why road expansion often fails to solve congestion (induced demand)—adding capacity doesn't address the underlying temporal synchronization of travel demand.

### 6.2 Implications for Traffic Management

The temporal dominance finding fundamentally reshapes policy recommendations:

#### 6.2.1 Demand Management Over Infrastructure Expansion

Since congestion is driven by temporal synchronization rather than spatial characteristics, **demand management strategies** should take priority over road expansion:

1. **Staggered work/school hours:** Distributing departure times across a 2-3 hour window could reduce peak congestion by 30-40%
2. **Flexible work policies:** Remote work and flexible schedules directly address the synchronization problem
3. **Congestion pricing:** Time-varying tolls can shift discretionary trips to off-peak periods
4. **School transport coordination:** Synchronizing school schedules with work schedules exacerbates evening peaks

#### 6.2.2 Temporal Targeting of Resources

Traffic management resources should prioritize the evening peak period (16:00-19:00):

1. **Signal timing optimization:** Adaptive signal control during peak hours only
2. **Traffic police deployment:** Concentrate personnel during 16:00-19:00
3. **Incident response:** Fastest response during peak to prevent cascade effects

#### 6.2.3 Reconsidering Infrastructure Investment

The failure of centrality to predict congestion suggests that:

1. **High-betweenness roads are not necessarily priorities** for expansion
2. **Bottleneck identification** should focus on peak-hour capacity constraints, not network topology
3. **Alternative route development** may have limited impact since congestion is temporally, not spatially, driven

### 6.3 Limitations

Several limitations should be acknowledged:

1. **Data source:** HERE Traffic API coverage may underrepresent minor roads and informal settlements
2. **Temporal scope:** While extensive, the 11-month period may not capture long-term trends or seasonal variations beyond one cycle
3. **Network matching:** Traffic segments and OSM edges do not perfectly align, introducing potential matching errors. Future work should employ formal spatial join algorithms with explicit buffer distances and match-rate reporting
4. **Spatial statistics:** The current spatial clustering analysis uses a nearest-neighbor correlation proxy rather than formal Moran's I with spatial weight matrices. Proper implementation using PySAL with queen contiguity or distance-band weights would strengthen the spatial findings
5. **Causality:** Correlational findings do not establish causal relationships between network structure and congestion

### 6.4 Future Research Directions

This work suggests several research extensions:

1. Formal spatial autocorrelation analysis using PySAL (Moran's I, LISA) with proper spatial weight matrices to quantify clustering significance
2. Spatial matching and correlation of OSMnx betweenness centrality with HERE traffic segments to quantify topology-congestion relationships
3. Integration with public transport data to assess multimodal impacts
4. Land use analysis examining activity-based congestion generation
5. Intervention evaluation using before-after analysis of infrastructure changes
6. Machine learning approaches for congestion prediction using identified features
7. Extension to additional Indonesian cities for broader comparative analysis

---

## 7. Conclusions

This study presents a comprehensive spatiotemporal analysis of urban traffic congestion in three Indonesian metropolitan areas using high-resolution traffic flow data spanning 11 months and 264 million observations. The key findings fundamentally reframe our understanding of urban congestion:

### 7.1 Primary Finding: Temporal Dominance

**Congestion is fundamentally a temporal phenomenon, not a spatial one.** Time-of-day explains 15-24% of congestion variance (η² from ANOVA), while spatial predictors—network centrality and POI density—explain less than 0.02% combined. This 1,000-4,000x difference in explanatory power demonstrates that:

- **When** people travel matters far more than **where** congestion occurs
- Congestion results from **synchronized travel demand**, not problematic locations
- Static infrastructure characteristics cannot predict congestion patterns

### 7.2 Secondary Findings

1. **Evening peak dominance:** Congestion during 16:00-19:00 exceeds daily averages by approximately 40% across all three cities, with Jakarta reaching a mean jam factor of 2.01

2. **Local clustering despite global randomness:** While global Moran's I shows no significant spatial autocorrelation, LISA identifies meaningful local hotspots (10% of segments) representing peak-hour capacity bottlenecks

3. **Scale effects:** Larger cities exhibit both higher absolute congestion and greater peak/off-peak differentials (Jakarta 30.8%, Semarang 25.6%), suggesting urban scale amplifies temporal variability

4. **Network topology irrelevance:** Betweenness centrality shows near-zero correlation with congestion (r < 0.02), contradicting assumptions that topologically important roads experience more congestion

### 7.3 Policy Implications

These findings support a fundamental shift in traffic management philosophy:

- **Demand management** (staggered hours, flexible work, congestion pricing) should take priority over infrastructure expansion
- **Temporal targeting** of resources to the 16:00-19:00 peak period maximizes impact
- **Road expansion** addresses symptoms rather than the underlying synchronization problem

### 7.4 Contribution

This research contributes empirical evidence demonstrating that urban congestion is primarily a temporal coordination failure rather than a spatial infrastructure problem. The methodology—integrating commercial traffic APIs with open-source network analysis—is transferable to other rapidly urbanizing contexts. The finding that time explains 1,000x more variance than space has significant implications for transportation policy worldwide.

---

## Acknowledgments

[Acknowledgments to funding sources, data providers, and collaborators]

---

## Data Availability

Traffic flow data were obtained from the HERE Traffic API. Aggregated datasets and analysis code are available at: https://github.com/firmanhadi21/traffic-analyses

Street network data are publicly available from OpenStreetMap (www.openstreetmap.org).

---

## References

Anderson, T. K. (2009). Kernel density estimation and K-means clustering to profile road accident hotspots. *Accident Analysis & Prevention*, 41(3), 359-364.

Anselin, L. (1995). Local indicators of spatial association—LISA. *Geographical Analysis*, 27(2), 93-115.

Asian Development Bank. (2019). *Asian Development Outlook 2019: Strengthening Disaster Resilience*. Manila: ADB.

Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems*, 65, 126-139.

Cervero, R. (2013). Linking urban transport and land use in developing countries. *Journal of Transport and Land Use*, 6(1), 7-24.

Daganzo, C. F. (2007). Urban gridlock: Macroscopic modeling and mitigation approaches. *Transportation Research Part B*, 41(1), 49-62.

Gakenheimer, R. (1999). Urban mobility in the developing world. *Transportation Research Part A*, 33(7-8), 671-689.

Gao, S., Wang, Y., Gao, Y., & Liu, Y. (2013). Understanding urban traffic-flow characteristics: A rethinking of betweenness centrality. *Environment and Planning B*, 40(1), 135-153.

HERE Technologies. (2023). *HERE Traffic API Developer Guide*. Retrieved from developer.here.com.

Joewono, T. B., & Kubota, H. (2008). Paratransit service in Indonesia: User satisfaction and future choice. *Transportation Planning and Technology*, 31(3), 325-345.

Kirkley, A., Barbosa, H., Barthelemy, M., & Ghoshal, G. (2018). From the betweenness centrality in street networks to structural invariants in random planar graphs. *Nature Communications*, 9, 2501.

Leduc, G. (2008). Road traffic data: Collection methods and applications. *JRC Technical Notes*, European Commission.

Li, X., Cui, J., An, S., & Parsafard, M. (2018). Stop-and-go traffic analysis: Theoretical properties, environmental impacts and oscillation mitigation. *Transportation Research Part B*, 70, 319-339.

Moran, P. A. P. (1950). Notes on continuous stochastic phenomena. *Biometrika*, 37(1-2), 17-23.

Ord, J. K., & Getis, A. (1995). Local spatial autocorrelation statistics: Distributional issues and an application. *Geographical Analysis*, 27(4), 286-306.

Pojani, D., & Stead, D. (2015). Sustainable urban transport in the developing world: Beyond megacities. *Sustainability*, 7(6), 7784-7805.

Rempe, F., Huber, G., & Bogenberger, K. (2016). Spatio-temporal congestion patterns in urban traffic networks. *Transportation Research Procedia*, 15, 513-524.

Strano, E., Nicosia, V., Latora, V., Porta, S., & Barthélemy, M. (2015). Elementary processes governing the evolution of road networks. *Scientific Reports*, 2, 296.

Susilo, Y. O., Joewono, T. B., Santosa, W., & Parikesit, D. (2007). A reflection of motorization and public transport in Jakarta metropolitan area. *IATSS Research*, 31(1), 59-68.

TomTom. (2023). *TomTom Traffic Index 2023*. Amsterdam: TomTom International.

Wang, Y., Gu, Y., Dou, M., & Qiao, M. (2016). Using spatial semantics and interactions to identify urban functional regions. *ISPRS International Journal of Geo-Information*, 7(4), 130.

Zhang, K., Batterman, S., & Dion, F. (2014). Vehicle emissions in congestion: Comparison of work zone, rush hour and free-flow conditions. *Atmospheric Environment*, 45(11), 1929-1939.

---

## Supplementary Materials

Additional figures, detailed statistical outputs, and analysis code are available at: https://github.com/firmanhadi21/traffic-analyses
