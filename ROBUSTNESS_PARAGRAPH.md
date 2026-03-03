# Robustness Check Paragraph — H3 Hexagonal Aggregation

## Placement in manuscript
Insert after the POI Density Analysis subsection (after Table 10a) and before the
Discussion section, as a new subsection:

  `\subsection{Robustness Check: Spatial Scale Sensitivity}`

Or, if preferred, as a paragraph appended to the Global Spatial Autocorrelation
subsection (after the sentence ending "...not an artifact of temporal averaging or
weight specification.").

---

## LaTeX version (ready to insert)

```latex
\subsection{Robustness Check: Spatial Scale Sensitivity (MAUP)}

To address the potential modifiable areal unit problem (MAUP)---the possibility
that null correlations reflect a mismatch between the road-segment unit of
analysis and the neighbourhood scale at which POI density and network centrality
actually operate---we re-ran all spatial correlations after aggregating variables
into Uber H3 hexagonal bins \citep{Brodsky2018} at two resolutions: resolution~8
(mean hex diameter $\approx$461\,m, area $\approx$0.46\,km$^2$, neighbourhood
scale) and resolution~9 (diameter $\approx$174\,m, area $\approx$0.10\,km$^2$,
block scale). For each hexagon, jam factor was computed as the observation-weighted
mean across all road segments and temporal periods falling within the cell
(235--1,836 hexagons per city at resolution~8; 490--5,319 at resolution~9). POI
counts and mean edge betweenness centrality were aggregated to the same hexagonal
grid using the same OSM data sources as the segment-level analyses.

POI-density and centrality correlations remained negligible at both resolutions
across all three cities (all $|\rho| < 0.08$, all $p > 0.07$; Table~\ref{tab:h3_robustness}).
The maximum observed effect was Semarang's POI Spearman $\rho = +0.077$
($p = 0.242$) at resolution~8, still far below conventional significance thresholds
and practically negligible in magnitude. These results confirm that the null
segment-level findings reported above are not an artefact of spatial scale: POI
density and network centrality do not predict congestion at any spatial grain tested,
from individual road segments to 461\,m neighbourhood hexagons.

Global Moran's I on hex-aggregated jam factor was non-significant for Semarang and
Bandung at both resolutions ($p > 0.05$), consistent with the segment-level finding.
Jakarta, however, exhibited weak but statistically significant positive spatial
autocorrelation at the neighbourhood scale at both resolutions
($I = 0.030$, $p = 0.033$ at resolution~8; $I = 0.022$, $p = 0.030$ at
resolution~9), a pattern not detectable at the road-segment level
($I = 0.003$, $p = 0.492$). This suggests that Jakarta's congestion has coherent
neighbourhood-level spatial structure---hexagons with elevated congestion tend to
be surrounded by similarly elevated neighbours---but this clustering is not
explained by POI density or betweenness centrality, both of which remain uncorrelated
with congestion even within Jakarta at the hex scale. The drivers of this weak but
consistent neighbourhood clustering in Jakarta warrant further investigation, with
candidate explanatory variables including land-use mix, population density, and
access to public transit.
```

---

## Plain-text version (for reference / co-author review)

To address the potential modifiable areal unit problem (MAUP) — the possibility
that null correlations reflect a mismatch between the road-segment unit of analysis
and the neighbourhood scale at which POI density and network centrality actually
operate — we re-ran all spatial correlations after aggregating variables into Uber
H3 hexagonal bins at two resolutions: resolution 8 (mean hex diameter ~461 m, area
~0.46 km², neighbourhood scale) and resolution 9 (diameter ~174 m, area ~0.10 km²,
block scale). For each hexagon, jam factor was computed as the observation-weighted
mean across all road segments and temporal periods falling within the cell
(235–1,836 hexagons per city at resolution 8; 490–5,319 at resolution 9). POI
counts and mean edge betweenness centrality were aggregated to the same hexagonal
grid using the same OSM data sources as the segment-level analyses.

POI-density and centrality correlations remained negligible at both resolutions
across all three cities (all |ρ| < 0.08, all p > 0.07). The maximum observed
effect was Semarang's POI Spearman ρ = +0.077 (p = 0.242) at resolution 8, still
far below conventional significance thresholds and practically negligible in
magnitude. These results confirm that the null segment-level findings reported
above are not an artefact of spatial scale: POI density and network centrality do
not predict congestion at any spatial grain tested, from individual road segments
to 461 m neighbourhood hexagons.

Global Moran's I on hex-aggregated jam factor was non-significant for Semarang and
Bandung at both resolutions (p > 0.05), consistent with the segment-level finding.
Jakarta, however, exhibited weak but statistically significant positive spatial
autocorrelation at the neighbourhood scale at both resolutions (I = 0.030, p = 0.033
at resolution 8; I = 0.022, p = 0.030 at resolution 9), a pattern not detectable at
the road-segment level (I = 0.003, p = 0.492). This suggests that Jakarta's
congestion has coherent neighbourhood-level spatial structure, but this clustering
is not explained by POI density or betweenness centrality, both of which remain
uncorrelated with congestion even within Jakarta at the hex scale. The drivers of
this weak but consistent neighbourhood clustering in Jakarta warrant further
investigation, with candidate explanatory variables including land-use mix,
population density, and access to public transit.

---

## Table to accompany the paragraph

\textbf{Table~\ref{tab:h3_robustness}.} H3 hex-level correlations — robustness check
(Spearman ρ; p-values in parentheses)

| City | Res | Hexes | POI ρ (p) | Centrality ρ (p) | Moran's I (p) |
|---|---|---|---|---|---|
| Semarang | 8 | 235 | +0.077 (0.242) | +0.053 (0.427) | −0.081 (0.087) |
| Semarang | 9 | 490 | +0.033 (0.462) | +0.022 (0.630) | +0.004 (0.443) |
| Bandung | 8 | 517 | +0.053 (0.228) | +0.041 (0.352) | +0.052 (0.055) |
| Bandung | 9 | 1,222 | +0.027 (0.339) | +0.053 (0.070) | −0.008 (0.412) |
| Jakarta | 8 | 1,836 | +0.021 (0.362) | −0.007 (0.784) | +0.030 (0.033)* |
| Jakarta | 9 | 5,319 | −0.014 (0.314) | −0.003 (0.836) | +0.022 (0.030)* |

*Segment-level baseline: POI ρ < 0.013 (all p > 0.6); Centrality ρ < 0.012
(all p > 0.44); Moran's I < 0.008 (all p > 0.35).*

\* p < 0.05
