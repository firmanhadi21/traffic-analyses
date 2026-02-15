# Journal Fit Assessment: Computers, Environment and Urban Systems (CEUS)

## Reviewer 1: GIS/Geospatial Methods Specialist

**Recommendation: Minor Revisions — Good fit for CEUS**

### Journal Fit Assessment

This manuscript aligns well with CEUS's core scope of "computer-based research on urban systems that privileges the geospatial perspective." The integration of HERE Traffic API data, OSMnx network analysis, PySAL geostatistics, and graph-based capacity detection represents exactly the kind of computational-geospatial urban analysis CEUS publishes. The application area (land use and transportation) is explicitly listed in the journal's scope.

### Strengths
1. **Impressive data scale:** 264 million observations across 3 cities over 11 months is a substantial empirical contribution. Few studies in the traffic-geospatial literature achieve this coverage.
2. **Methodological integration:** The pipeline combining commercial API data (HERE) with open-source tools (OSMnx, PySAL, GeoPandas) is reproducible and transferable — a strong match for CEUS's emphasis on computational innovation.
3. **Novel capacity drop framework:** The graph-based capacity drop detection using directed network topology is a genuine methodological contribution.
4. **Triangulated null findings:** Testing the spatial hypothesis from four independent angles (centrality, POI, capacity, capacity drops) strengthens the temporal dominance claim considerably.

### Concerns

1. **Spatial weights specification:** The manuscript mentions "queen contiguity" for Moran's I (Section 4.3.1) but then reports using "K-nearest neighbors (k=8)" in the results (Table 7). These are different spatial weight matrices with different implications. Please clarify and justify the final choice. For linear road segments, KNN is more appropriate than queen contiguity — but the inconsistency needs resolving.

2. **Modifiable Areal Unit Problem (MAUP):** Traffic segments vary substantially in length. The geostatistical analysis treats each segment as a spatial unit of equal weight, but a 3 km motorway segment and a 200 m tertiary road segment contribute equally. Discuss how segment length heterogeneity might affect Moran's I and LISA results.

3. **Spatial matching methodology:** The 200m nearest-neighbor centroid matching between HERE segments and OSMnx edges (Section 4.5.1) is pragmatic but could introduce systematic bias. What proportion of matches are within 50m? 100m? A match quality distribution would strengthen confidence in the centrality-congestion correlations.

4. **Missing computational details:** CEUS readers expect reproducibility. What was the spatial weight distance threshold for LISA? How were edge betweenness values computed — weighted by distance or unweighted? Were directed or undirected graphs used for centrality?

5. **Visualization:** Several figures are referenced but I'd recommend adding an integrated analytical framework diagram showing the data flow pipeline — from raw API data through aggregation, spatial matching, to each analysis branch. CEUS readers value workflow clarity. *(Note: Figure 1 is referenced but its quality/content wasn't reviewed.)*

### Minor Issues
- Table 3: Evening Peak (16:00-18:59) and Evening Off-Peak (20:00-21:59) have a gap at 19:00-19:59. Is this intentional?
- Section numbering: 5.4.2 (Street Orientation) appears after 5.6, breaking the logical flow.
- The word count (6,261) is appropriate for CEUS.

---

## Reviewer 2: Transportation Science / Urban Planning Specialist

**Recommendation: Major Revisions — Conditional fit for CEUS**

### Journal Fit Assessment

The paper falls within CEUS's "land use and transportation" application area, and the computational methodology is appropriate for the journal. However, CEUS increasingly expects papers to go beyond descriptive analysis toward **predictive modeling, decision support, or actionable computational tools** — areas where this manuscript is thin.

### Strengths
1. **Important empirical finding:** The 1,000-4,000x temporal-over-spatial dominance is a striking result that challenges conventional infrastructure-focused planning approaches. If it holds, it has significant policy implications.
2. **Multi-city comparative design:** The three-city comparison across different urban scales adds generalizability.
3. **Honest treatment of null results:** The authors handle the null spatial findings with appropriate nuance, especially the jam factor normalization discussion (Section 5.5.4).

### Major Concerns

1. **The central finding is partially an artifact of the metric:**
   The authors acknowledge (Section 5.5.4) that the HERE jam factor normalizes speed to free-flow, inherently removing capacity effects. This is a **fundamental methodological limitation**, not just a caveat. The claim "spatial factors don't matter" is more accurately "spatial factors are invisible in this metric." The paper's strongest claim — temporal dominance over spatial factors — is overstated given that the dependent variable *by design* cannot detect spatial capacity effects.

   **Required revision:** Either (a) reframe the central finding as "temporal dominance in *relative* congestion" rather than congestion generally, or (b) supplement with absolute speed/delay analysis to confirm the finding holds with unnormalized data.

2. **Comparing apples and oranges (eta-squared vs R-squared):**
   Table 11a compares ANOVA eta-squared (15-24%) with Pearson R-squared (<0.02%). But eta-squared from an 8-category ANOVA is not directly comparable to R-squared from a bivariate continuous correlation. A fair comparison would require entering temporal period as a predictor in the same regression model alongside spatial variables. Without this, the "1,000-4,000x" ratio is methodologically misleading.

   **Required revision:** Conduct a multiple regression or random forest feature importance analysis that includes both temporal and spatial predictors in the same model.

3. **Ecological fallacy risk:**
   The analysis uses segment-level *means* aggregated over 11 months. This averaging eliminates within-segment temporal variance — which is precisely what the temporal ANOVA measures at the raw observation level. The spatial analyses operate on a different aggregation level than the temporal analyses, making direct comparison problematic.

4. **Missing traffic flow/volume data:**
   The jam factor tells us about *relative* congestion but nothing about *absolute* traffic volumes. Network centrality theory predicts that high-betweenness roads carry more *volume*, not necessarily more *relative delay*. Without volume data, the centrality-congestion null finding has limited theoretical implications. Betweenness centrality may indeed predict traffic volume perfectly while showing no correlation with jam factor.

5. **Policy recommendations are too strong for the evidence:**
   Recommending against infrastructure expansion based on null correlations with a normalized metric is a significant policy leap. The conclusion that "road expansion often fails to solve congestion" (Section 6.1.6) cites induced demand theory but provides no evidence from this study.

6. **Limited computational novelty:**
   For CEUS, the computational methodology is relatively standard (Moran's I, LISA, OSMnx centrality, Pearson/Spearman correlations). The journal typically expects more advanced methods — machine learning, simulation, optimization, or novel algorithms. The capacity drop detection is interesting but straightforward graph traversal.

### Minor Concerns
- The literature review could better engage with CEUS-published work on urban analytics and GIS-based transportation analysis.
- No validation against ground truth (traffic counts, loop detectors, etc.).
- The study period starts in March 2025 — is the data actually available? This seems to be a future date depending on the review timeline.

---

## Reviewer 3: Spatial Statistics / Quantitative Geography Specialist

**Recommendation: Minor Revisions — Good fit for CEUS**

### Journal Fit Assessment

The paper makes a compelling empirical contribution using geospatial and geostatistical methods applied to urban transportation — squarely within CEUS's scope. The spatial analysis is thorough and the findings, while largely negative (null spatial effects), are scientifically valuable. CEUS has published similar "null-but-important" spatial studies before.

### Strengths

1. **Rigorous geostatistical pipeline:** The progression from global Moran's I to LISA to Getis-Ord Gi* follows best practices in spatial analysis. The decision to test both global and local patterns is well-justified.
2. **Effect size reporting:** The consistent use of Cohen's d alongside p-values throughout the bottleneck analysis (Tables 10c-10f) is exemplary. Too many spatial studies rely solely on p-values.
3. **The temporal dominance finding is genuinely important** for urban spatial analysis theory. If spatial characteristics don't predict congestion, this challenges core assumptions in GIS-based transportation planning.
4. **Reproducible toolchain:** Python + GeoPandas + PySAL + OSMnx + NetworkX is a standard, reproducible stack. The code availability on GitHub is a strong positive.

### Concerns

1. **Spatial weight matrix sensitivity:**
   Only one spatial weight specification (KNN, k=8) is reported for Moran's I. Spatial autocorrelation results are known to be sensitive to weight matrix specification. Please provide sensitivity analysis with k=4, k=12, and distance-band weights (e.g., 500m, 1000m). If Moran's I remains non-significant across all specifications, the null finding is more robust.

2. **Multiple testing correction:**
   LISA produces significance tests for every segment (18,694 total). At alpha=0.05, approximately 935 segments would appear significant by chance alone. The reported significant segments (1,535 in Jakarta, 320 in Bandung, 78 in Semarang) should be evaluated against this baseline. Jakarta and Bandung exceed the chance expectation, but Semarang's 78 is *below* it — suggesting its LISA clusters may be spurious. Apply FDR (Benjamini-Hochberg) correction and report adjusted results.

3. **Spatial regression, not just correlation:**
   The centrality-congestion relationship is tested only with bivariate Pearson/Spearman correlations. This ignores spatial dependence in residuals. A Spatial Lag or Spatial Error model (via PySAL's spreg) would properly account for spatial structure. If the spatial regression coefficient for centrality remains non-significant, the null finding is much stronger.

4. **Temporal aggregation issue for spatial analysis:**
   The LISA and Moran's I are computed on mean jam factor per segment (averaged over 11 months). This temporal averaging may mask time-specific spatial patterns. Consider computing Moran's I separately for each temporal period — spatial clustering might emerge during evening peak even if absent in the overall mean. You mention "evening peak" for LISA in Table 8, but Table 7's global Moran's I doesn't specify which temporal aggregation was used.

5. **Getis-Ord Gi* results:**
   Figures for Getis-Ord Gi* are listed in the figures directory (e.g., `bdg_getis_ord_gi.png`) but I don't see formal results presented in the text with the same rigor as LISA. Add a summary table of Gi* hot/cold spot counts and compare with LISA findings for methodological triangulation.

6. **Correlogram interpretation:**
   Correlograms are produced (figures directory) but not discussed in the text. Spatial correlograms would reveal whether autocorrelation exists at specific distance bands even if global Moran's I is non-significant. This is important — congestion could cluster at 500m scales (neighboring segments) while being random at city-wide scales.

### Minor Issues
- Consider computing bivariate Moran's I (centrality vs. jam factor) as an alternative to Pearson correlation — it would account for spatial structure in the relationship.
- The POI buffer radius (300m) should be justified. Sensitivity to 100m, 200m, 500m would strengthen the null finding.
- Report the spatial lag of congestion as a predictor — neighboring segment congestion might predict local congestion even if centrality doesn't.

---

## Summary Across Reviewers

| Aspect | Reviewer 1 (GIS) | Reviewer 2 (Transport) | Reviewer 3 (Spatial Stats) |
|--------|------------------|------------------------|---------------------------|
| **Journal Fit** | Good | Conditional | Good |
| **Recommendation** | Minor Revisions | Major Revisions | Minor Revisions |
| **Key Concern** | Methodological consistency | Jam factor normalization artifact | Spatial weight sensitivity |
| **Computational Novelty** | Adequate | Insufficient | Adequate |
| **Central Finding** | Convincing | Overstated | Convincing if confirmed |

**Consensus:** The paper is a reasonable fit for CEUS but requires: (1) addressing the jam factor normalization limitation more honestly or with supplementary unnormalized analysis, (2) improving statistical rigor (spatial regression, multiple testing correction, weight sensitivity), and (3) resolving internal inconsistencies (spatial weights, section ordering, temporal period gaps).
