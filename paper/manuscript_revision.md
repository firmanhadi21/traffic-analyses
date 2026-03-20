# Manuscript Revision Log

## Rejection from CEUS (March 2026)

**Journal**: Computers, Environment and Urban Systems (Special Issue: Open Urban Data Science)
**Decision**: Desk rejection
**Editor feedback**: "Does not meet the required quality standards" (no reviewer comments)
**Diagnosis**: Likely desk rejection — editor did not send to reviewers

### Critical Issues Identified

1. **Circular reasoning in central finding** — HERE jam factor normalizes to free-flow speed, which removes capacity effects by design. Finding that capacity doesn't predict congestion may be tautological.

2. **Unfair temporal vs spatial comparison** — Comparing eta-squared from 8-level categorical ANOVA against R-squared from continuous spatial predictors is methodologically asymmetric. A multilevel/mixed model would be fairer.

3. **Redundant structure** — Introduction and Literature Review covered the same ground (probe data, OSMnx, spatial autocorrelation, Indonesian studies).

4. **Null-result framing** — Four null tests presented as main contribution without enough engagement with *why* spatial factors fail.

### Major Issues Identified

5. **Broken LaTeX** — 7 missing `\includegraphics` backslashes, 1 missing `\caption` backslash, non-standard `\subsubsubsection` commands. Figures likely broken in submitted PDF.

6. **Placeholder text** — `[funding source]` and `[institution]` in Acknowledgements.

7. **Weak theoretical grounding** — Many methods applied without clear theoretical model guiding hypothesis development.

8. **Overemphasized software section** — ~600 words describing every script, reads as documentation rather than research contribution.

### Minor Issues

- Missing `\begin{document}` in LaTeX
- No CRediT author statement (required by Elsevier)
- Abstract too number-heavy

---

## Track A — Editorial Fixes (COMPLETED)

All changes applied to `paper/ceus_manuscript.tex`:

| # | Change | Commit |
|---|--------|--------|
| 1 | Fixed 7 broken `\includegraphics` commands | e5dac0c |
| 2 | Fixed 1 broken `\caption` command | e5dac0c |
| 3 | Replaced `\subsubsubsection` with `\paragraph` | e5dac0c |
| 4 | Added missing `\begin{document}` | e5dac0c |
| 5 | Merged Introduction + Literature Review into single Introduction | e5dac0c |
| 6 | Rewrote abstract — narrative flow, less number-heavy, "when vs where" framing | e5dac0c |
| 7 | Trimmed Python package section from ~600 to ~150 words | e5dac0c |
| 8 | Fixed placeholder acknowledgements | e5dac0c |
| 9 | Added CRediT author statement | e5dac0c |
| 10 | Strengthened Discussion — jam factor circularity, expanded policy implications | e5dac0c |
| 11 | Expanded limitations and future research directions | e5dac0c |
| 12 | Removed `paper/` from `.gitignore` to track source files | e5dac0c |

Unique references from deleted Literature Review (Batty 2013, Saberi 2020, Kirkley 2018, Tobler 1970, bottleneck theory) were integrated into the Introduction.

---

## Track B — Methodological Improvements (IN PROGRESS)

Colab notebook prepared: `speed_aggregation_colab.ipynb`

### B1 — Speed aggregation & ANOVA (Steps 1–5)
- Streaming aggregation (Welford's algorithm) — safe for 264M rows on Colab 12 GB RAM
- ANOVA on absolute speed, speed reduction, free-flow speed, and jam factor
- If eta² values are similar across metrics → circularity critique refuted

### B2 — Speed-based spatial correlations (Steps 6–7)
- Downloads OSM networks, computes edge betweenness centrality
- Correlates centrality against jam factor, current speed, speed reduction, free-flow speed
- If R² remains < 0.01 for absolute speed → null spatial finding is genuine

### B3 — Multilevel model (Steps 8–9)
- Mixed-effects model: `speed_mean ~ C(time_period) + betweenness + free_flow_mean + (1|fid)`
- Null model → ICC (between-segment vs within-segment variance)
- Temporal model → pseudo-R² for time period
- Full model → incremental R² for spatial predictors beyond temporal
- Replaces the unfair eta-squared vs R-squared comparison

### Output (Step 10)
- Ready-to-paste LaTeX tables for all three analyses
- CSV exports: `anova_comparison_all_metrics.csv`, `centrality_correlations_all_metrics.csv`, `multilevel_model_results.csv`

### Status
- [x] B1: Speed aggregation & ANOVA — completed via `run_speed_aggregation.py` (Feb 16)
- [x] B2: Speed-based spatial correlations — completed via `speed_spatial_analysis.py` (Mar 10)
- [x] B3: Multilevel model — completed via `speed_spatial_analysis.py` (Mar 10)
- [x] Results integrated into `paper/ceus_manuscript.tex`

### B2 + B3 Results Summary (March 10, 2026)

**B1 ANOVA results (all cities):**
- jam_factor η² = 8.2–9.4%, speed η² = 5.1–5.9%, speed_reduction η² = 8.2–9.6%, free_flow η² ≈ 0%
- Temporal dominance confirmed for absolute speed metrics — not a normalization artifact

**B2 Centrality correlations (evening peak):**
| Metric | SMG R² | BDG R² | JKT R² |
|--------|--------|--------|--------|
| Jam factor | 0.084 | 0.136 | 0.064 |
| Current speed | 0.003 | 0.000 | 0.001 |
| Speed reduction | 0.108 | 0.130 | 0.067 |
| Free-flow speed | 0.019 | 0.049 | 0.031 |

Key finding: Centrality correlates moderately with jam factor and speed reduction (which incorporate free-flow normalization) but NOT with absolute current speed (R² < 0.003). This confirms centrality's "effect" on jam factor is mediated through free-flow speed (road design), not congestion severity.

**B3 Multilevel model (absolute speed):**
| City | ICC | Temporal R² | Spatial ΔR² | β_centrality |
|------|-----|-------------|-------------|--------------|
| Semarang | 89.4% | 67.0% | 79.1% | −2,379*** |
| Bandung | 87.8% | 63.1% | 74.0% | −5,632*** |
| Jakarta | 89.1% | 56.5% | 77.6% | −27,605*** |

Key finding: ICC ~88-89% means most speed variance is between segments (road type differences). Time explains 57–67% of within-segment fluctuations. Spatial ΔR² of 74–79% is driven almost entirely by free_flow_mean (road capacity proxy); centrality alone adds <1%.

### Manuscript changes made
- Methods: Added speed validation paragraph in Section 3.2; new Multilevel Variance Decomposition subsection
- Results: Added Table speed_validation (cross-metric ANOVA); replaced centrality table with cross-metric version; replaced η² vs R² table with multilevel decomposition table
- Discussion: Transformed circularity from limitation to resolved concern; updated limitations (removed 2 addressed items); updated future work (removed 2 completed items)
- Conclusion: Replaced "1,000–4,000×" framing with multilevel model results
- Abstract: Updated to reflect multilevel model framing

---

## Track C — Journal Retargeting (COMPLETED)

**New target**: Transportation Research Interdisciplinary Perspectives (TRIP)

### Why TRIP is a good fit
- Part of Transportation Research family (credibility)
- Interdisciplinary scope matches paper's mix of GIS, network science, transport planning
- **Explicitly welcomes negative/null results and less mature ideas** (from journal aims & scope)
- Gold Open Access only (APC: USD $2,130) — no OA vs subscription bias concern

### TRIP Requirements
| Requirement | Status |
|-------------|--------|
| Abstract max 250 words | Done |
| Keywords 1-7 | Done (reduced to 7) |
| Author-year (Harvard) citations | Done (reference list reformatted) |
| Highlights | Done (reframed to multilevel model) |
| Graphical abstract | Already have (`paper/graphical-abstract.png`) |
| Cover letter | Done (reframed to multilevel model, dated March 20) |

### Changes applied (March 20, 2026)
- Reference format: `(1995).` → `, 1995.` across all 50 references
- Keywords: Reduced from 9 to 7 (added "Demand synchronization", "Multilevel model", "OpenStreetMap"; removed "Jam factor", "Capacity bottleneck", "HERE Traffic API", "Spatial autocorrelation", "OSMnx")
- Cover letter: Replaced η²/R² framing with multilevel model language (57–67% temporal, <1% spatial); added positive-control and cross-metric validation; updated date
- Highlights: Reframed around multilevel model findings and positive-control test

---

## Publishing Model Discussion

User asked whether choosing subscription (free) vs open access (APC) affects acceptance. Conclusion: **no credible evidence** of bias at hybrid journals. Editorial decisions are firewalled from publishing model choices. TRIP is OA-only so the question is moot for this submission.
