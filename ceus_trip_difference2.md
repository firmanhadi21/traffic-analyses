# Differences Between `firmanhadi_ceus_v2.tex` and `trip_manuscript.tex`

## Summary

These are **substantially different manuscripts** — not just reformatted versions. `firmanhadi_ceus_v2.tex` is the pre-revision CEUS submission (desk-rejected), while `trip_manuscript.tex` is the heavily revised version retargeted for TRIP. The revision addressed critical methodological issues identified after the CEUS rejection.

| Aspect | `firmanhadi_ceus_v2.tex` (CEUS) | `trip_manuscript.tex` (TRIP) |
|--------|--------------------------------|------------------------------|
| Central framing | "Temporal synchronization" — 1,000-4,000x ratio | "Demand synchronization" — 57-67% within-segment speed |
| Core method | eta-squared vs R-squared comparison | Multilevel mixed-effects model |
| Metric validation | Jam factor only | Cross-metric (speed, speed reduction, free-flow, jam factor) |
| Positive control | None | Free-flow speed as spatial predictor (R² = 0.60-0.71) |
| Status | Desk-rejected from CEUS | Revised for TRIP submission |

---

## Major Content Differences

### 1. Central Finding Reframed

- **CEUS v2**: "temporal factors dominate spatial factors by 1,000-4,000x" based on comparing eta-squared (15-24%) from ANOVA vs R-squared (<0.01%) from bivariate correlations — a methodologically asymmetric comparison flagged as misleading
- **TRIP**: "demand synchronization — time-of-day explains 57-67% of within-segment speed fluctuations, while network centrality adds less than 1% beyond road type" — based on a proper multilevel variance decomposition using the same model framework

### 2. Separate Literature Review Eliminated

- **CEUS v2**: Has a standalone Section 2 "Literature Review" (~400 words) repeating material from the Introduction (probe data, OSMnx, spatial autocorrelation, bottleneck theory)
- **TRIP**: Literature Review merged into Introduction; unique references (Batty 2013, Saberi 2020, Kirkley 2018, Tobler 1970) integrated into the relevant Introduction paragraphs

### 3. Multilevel Model Added (New in TRIP)

- **CEUS v2**: No multilevel model; relies on the eta-squared vs R-squared comparison (Table 17) which is not a fair apples-to-apples comparison
- **TRIP**: New Section 3.6 "Multilevel Variance Decomposition" with three nested mixed-effects models (null → temporal → full), ICC partitioning, pseudo-R², and incremental ΔR². Results in new Table (multilevel) showing ICC ~88-89%, temporal R² 57-67%, spatial ΔR² 74-79% (driven by free-flow speed, not centrality)

### 4. Cross-Metric Speed Validation Added (New in TRIP)

- **CEUS v2**: All analyses use only jam factor, leaving the circularity critique unaddressed (jam factor normalizes to free-flow speed, removing capacity effects by design)
- **TRIP**: ANOVA repeated on absolute speed, speed reduction, and free-flow speed. New Table (speed_validation) shows eta² is similar across metrics (8-10% for jam factor and speed reduction, 5-6% for speed, ~0% for free-flow), confirming temporal dominance is not a normalization artifact

### 5. Positive Control Test Added (New in TRIP)

- **CEUS v2**: No positive control — the null spatial finding could be due to methodological issues (bad spatial matching, insufficient power, data quality)
- **TRIP**: New "Positive Control" paragraph showing free-flow speed explains 60-71% of current speed variance (R² = 0.60-0.71), proving the pipeline detects known spatial relationships. The same pipeline that finds strong spatial structure in road design (R² = 0.60-0.71) finds none in congestion (R² < 0.003)

### 6. Centrality Table Redesigned

- **CEUS v2**: Table 10 shows bivariate centrality-congestion correlations (Pearson r, Spearman ρ) for jam factor only
- **TRIP**: Table (centrality_speed) shows Pearson R² for four metrics: jam factor, current speed, speed reduction, free-flow speed. Reveals the key insight: centrality correlates moderately with jam factor (R² = 0.06-0.14) but near-zero with absolute speed (R² < 0.003), because the apparent effect is mediated through free-flow speed

### 7. Python Package Section Trimmed

- **CEUS v2**: ~600 words describing every script, stage, and dependency — reads as software documentation rather than research contribution
- **TRIP**: ~150 words summarizing the pipeline in one paragraph (Section 3.7)

### 8. Temporal vs Spatial Comparison Table Removed

- **CEUS v2**: Table 17 explicitly shows the problematic 1,000-4,000x ratio comparing eta-squared against R-squared, with a "Ratio (Temporal/Spatial)" row
- **TRIP**: This table is replaced by the multilevel model table, which provides a fair comparison within the same statistical framework

### 9. Comparative City Analysis Section Removed

- **CEUS v2**: Section 5.7 with Tables 18-19 comparing peak/off-peak ratios and scaling relationships across cities
- **TRIP**: This standalone section removed; the key finding (evening peak ~40% above daily average) is integrated into the temporal patterns section

### 10. Jam Factor Normalization Section Restructured

- **CEUS v2**: Section 5.5.4 "HERE Jam Factor Normalization" as a standalone results subsection explaining the formula JF ∝ 1 - v/v_free-flow
- **TRIP**: Circularity concern addressed throughout — in Methods (speed chosen over jam factor for multilevel model), Results (cross-metric validation), and Discussion (resolved rather than flagged as limitation)

### 11. Discussion Reframed

- **CEUS v2**: Leads with "The Failure of Spatial Predictors and Capacity Constraints" — a null-result framing
- **TRIP**: Leads with "urban congestion operates fundamentally as a demand synchronization problem" — a positive-finding framing supported by the multilevel model, positive control, and cross-metric validation

### 12. Conclusion Structure Simplified

- **CEUS v2**: Subsections (6.1 Primary Finding, 6.2 Secondary Findings, 6.3 Policy Implications)
- **TRIP**: Single flowing section without subsections

### 13. Hotspot Figures

- **CEUS v2**: Shows all three city hotspot maps as main figures
- **TRIP**: Shows only Jakarta hotspot map; Bandung and Semarang moved to Supplementary Figures S1-S2

### 14. Title and Author Block

- **CEUS v2**: Includes `\title{}`, `\author{}`, `\maketitle` with full affiliations
- **TRIP**: No title/author block in the .tex file (likely handled by journal submission system)

### 15. Different Data Values in Some Tables

- **POI table** (Table 11): CEUS v2 has different correlation values (e.g., Jakarta Pearson r = 0.008) vs TRIP (Jakarta Pearson r = -0.0005) — likely from re-running with updated methodology
- **Capacity tables**: CEUS v2 reports evening-peak JF values (~1.65-2.01); TRIP reports overall mean JF values (~1.15-1.43) with different column structure
- **Bottleneck tables**: Different values reflecting re-analysis

---

## Formatting Differences

| Aspect | CEUS v2 | TRIP |
|--------|---------|------|
| Keywords | 9 (tool-specific) | 7 (concept-focused, adds "Demand synchronization", "Multilevel model") |
| Section headings | `\subsubsection` | `\paragraph` |
| Reference style | Author (Year) with parentheses | Author, Year with commas |
| Reference list | ~50 refs (some commented out) | ~40 refs (cleaned up, added new ones) |
| Dashes | Unicode em/en-dashes | LaTeX `---`/`--` |
| Figure paths | `figures/` | `../figures/` |
| Back matter | Separate Declaration, Ethics, Funding sections | Consolidated Acknowledgements + CRediT |

---

## Conclusion

`trip_manuscript.tex` is a **major revision** of `firmanhadi_ceus_v2.tex`, not a reformatted copy. The revision:

1. **Fixed the core methodological flaw** — replaced the asymmetric eta²/R² comparison with a multilevel model
2. **Addressed the circularity critique** — added cross-metric validation using absolute speed
3. **Added the positive control** — proving the pipeline works for spatial detection
4. **Reframed from null-result to positive finding** — "demand synchronization" instead of "failure of spatial predictors"
5. **Streamlined structure** — merged Literature Review, trimmed software section, simplified conclusion

The CEUS v2 version (`firmanhadi_ceus_v2.tex`) represents the desk-rejected submission; `trip_manuscript.tex` is the methodologically strengthened version targeting TRIP.
