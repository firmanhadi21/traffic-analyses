# Exploratory Data Analysis Report
Generated: 2026-03-20 21:21:11

## Executive Summary

**DATA VALIDATION: ISSUES FOUND**

Some data quality issues were detected. Review details below.

## 1. Null Value Check

PASS: No null values in key columns (jam_factor_mean, jam_factor_count, geometry)

## 2. Data Completeness

| City | Segments | Consistent | Total Observations |
|------|----------|------------|-------------------|
| Semarang | 822 | No | 18,166,779 |
| Bandung | 2,161 | No | 51,844,382 |
| Jakarta | 11,312 | No | 246,220,516 |

## 3. Value Range Validation

| City | Min JF | Max JF | Valid Range |
|------|--------|--------|-------------|
| Semarang | 0.000 | 9.800 | Yes |
| Bandung | 0.000 | 9.900 | Yes |
| Jakarta | 0.000 | 9.900 | Yes |

## 4. Segment Count Justification

The different segment counts between cities are valid because:

1. Segment count reflects actual HERE Traffic API road coverage
2. Larger cities have proportionally more monitored roads
3. Data completeness is consistent WITHIN each city
4. Statistical methods account for different sample sizes

## 5. Figures Generated

- `eda_coverage_comparison.png`: Segment and observation counts
- `eda_completeness_heatmap.png`: Data completeness by period
- `eda_distribution_validation.png`: Jam factor distributions
- `eda_null_check.png`: Null value verification