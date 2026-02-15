# HPC Workflow for Traffic Congestion Analysis

This document describes the procedure for running advanced spatial analyses on HPC and updating the research manuscript with the results.

---

## Overview

### What Has Been Completed (Local Machine)

| Analysis | Status | Output |
|----------|--------|--------|
| Evening Peak time fix (16:00-18:59) | ✅ Done | `paper/manuscript.md` |
| Global Moran's I | ✅ Done | `analysis_results/morans_i_results.csv` |
| LISA cluster analysis | ✅ Done | `analysis_results/lisa_results.csv` |
| ANOVA + Tukey HSD | ✅ Done | `analysis_results/anova_results.csv` |
| LISA cluster maps | ✅ Done | `figures/*_lisa_clusters.png` |

### What Needs HPC (Computationally Intensive)

| Analysis | Script | Reason |
|----------|--------|--------|
| Centrality-Congestion Correlations | `compute_centrality_correlations.py` | Jakarta network has ~45,000 nodes; betweenness centrality is O(VE) complexity |
| Bottleneck Analysis | `bottleneck_analysis.py` | Downloads OSMnx road network for 3 cities; graph-based capacity drop detection |
| **Revision Analyses** | `revision_analyses.py` | Spatial weight sensitivity, FDR LISA, period-specific Moran's I, spatial regression, Gi*, match quality, POI buffer sensitivity |

---

## Step 1: Transfer Files to HPC

### Option A: Download from GitHub
```bash
# On HPC
git clone https://github.com/YOUR_USERNAME/traffic-analyses.git
cd traffic-analyses
tar -xzvf traffic_hpc.tar.gz
```

### Option B: Direct Upload
```bash
# From local machine
scp traffic_hpc.tar.gz username@hpc.server.edu:~/

# On HPC
tar -xzvf traffic_hpc.tar.gz
```

### Extracted Contents
```
traffic_hpc/
├── compute_centrality_correlations.py   # Centrality analysis script
├── bottleneck_analysis.py               # Bottleneck analysis script
├── revision_analyses.py                 # Revision analyses (reviewer responses)
├── advanced_spatial_analysis.py         # Already completed analyses
├── requirements_hpc.txt                 # Python dependencies
├── requirements_revision.txt            # Additional deps for revision (spreg)
├── run_hpc.sh                           # SLURM job script
├── traffic_smg_output/                  # Semarang data (8 files)
├── traffic_bdg_output/                  # Bandung data (8 files)
├── traffic_jkt_output/                  # Jakarta data (8 files)
└── analysis_results/                    # Existing results
```

---

## Step 2: Set Up Python Environment on HPC

```bash
# Load Python module (adjust for your HPC system)
module load python/3.11
module load gdal/3.6        # Required for geopandas
module load proj/9.0        # Required for spatial operations

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements_hpc.txt
pip install -r requirements_revision.txt
```

### Required Packages
- `osmnx>=1.6.0` - Street network download
- `networkx>=3.0` - Graph analysis & betweenness centrality
- `geopandas>=0.14.0` - Spatial data handling
- `scipy>=1.10.0` - Statistical tests
- `esda>=2.5.0` - Spatial statistics (if re-running Moran's I)
- `libpysal>=4.9.0` - Spatial weights

---

## Step 3: Run Centrality Analysis

### Option A: Interactive Session (Recommended for Testing)
```bash
# Request interactive node
srun --time=04:00:00 --mem=32G --cpus-per-task=4 --pty bash

# Activate environment
source venv/bin/activate

# Run analysis
python compute_centrality_correlations.py
```

### Option B: Batch Job Submission
```bash
# Edit run_hpc.sh if needed (adjust SLURM parameters)
nano run_hpc.sh

# Submit job
sbatch run_hpc.sh

# Monitor job
squeue -u $USER
tail -f centrality_*.out
```

### Expected Runtime
| City | Nodes | Estimated Time |
|------|-------|----------------|
| Semarang | ~12,000 | 5-10 minutes |
| Bandung | ~18,000 | 15-30 minutes |
| Jakarta | ~45,000 | 1-2 hours |
| **Total** | - | **2-3 hours** |

### Expected Output
```
analysis_results/centrality_correlations.csv
```

With columns:
- `city`: City name
- `n_matched`: Number of matched segments
- `match_rate`: Percentage of traffic segments matched to OSM
- `pearson_r`: Pearson correlation coefficient
- `pearson_p`: Pearson p-value
- `spearman_r`: Spearman correlation coefficient
- `spearman_p`: Spearman p-value

---

## Step 3b: Run Bottleneck Analysis

This analysis tests whether congestion concentrates at capacity-constrained road segments (bottlenecks) vs. activity centers.

### Key Design Decision: Network Filtering

HERE Traffic covers only major roads (motorways through tertiary). The OSMnx network is **filtered to HERE-comparable road types** before analysis to prevent matching errors between HERE arterial data and unmonitored residential streets.

### Running the Analysis

```bash
# Interactive session
srun --time=02:00:00 --mem=16G --cpus-per-task=2 --pty bash
source venv/bin/activate

python bottleneck_analysis.py
```

### What It Does

1. **Downloads OSMnx road network** for each city (cached after first download)
2. **Filters** to motorway through tertiary roads (+ link types)
3. **Spatial joins** HERE traffic segments to filtered OSMnx edges (nearest-neighbor, max 0.002°)
4. **Aggregate capacity test**: Low vs high capacity road congestion comparison
5. **Graph-based capacity drop detection**: Finds nodes where incoming capacity > outgoing capacity (≥20% reduction)
6. **Proximity to capacity drops**: Tests if segments near drop nodes are more congested
7. **Local capacity gradient**: Identifies segments with lower capacity than K=10 nearest neighbors (local bottlenecks)

### Expected Runtime
| City | Estimated Time |
|------|----------------|
| Semarang | 1-2 minutes |
| Bandung | 2-5 minutes |
| Jakarta | 5-15 minutes |
| **Total** | **~20 minutes** |

### Expected Output

**CSV results:**
```
analysis_results/bottleneck_analysis_results.csv
```

Key columns:
- `city`: City name
- `low_cap_jf`, `high_cap_jf`: Mean JF for low/high capacity roads
- `cap_p_value`, `cap_effect_size`: Statistical significance of capacity effect
- `n_capacity_drops`: Number of capacity drop nodes detected
- `near_drop_jf`, `far_drop_jf`: JF near vs far from capacity drops
- `drop_prox_p_value`: Significance of proximity-to-drop effect
- `local_bn_effect_size`: Cohen's d for local bottleneck effect
- `local_drop_pearson_r`: Correlation between local capacity deficit and congestion

**Figures:**
```
figures/bottleneck_capacity_comparison.png      # Box plot: low vs high capacity
figures/capacity_congestion_scatter.png         # Scatter: capacity vs JF
figures/capacity_drop_spatial_analysis.png      # Capacity drop proximity + local bottleneck
```

### Interpreting the Results

| Result | Meaning |
|--------|---------|
| Near-drop JF > Far-drop JF (p < 0.05) | Spatial bottleneck hypothesis **supported** |
| Local bottleneck d > 0.2 | Relative capacity deficit predicts congestion |
| All tests non-significant | Congestion is **temporal/demand-driven**, not capacity-constrained |
| Weak r but significant local d | **Relative** capacity matters more than **absolute** capacity |

**Note on HERE jam factor normalization:** JF is normalized to each road's free-flow speed, which partially removes capacity effects. Spatial capacity transitions (relative measures) are stronger tests than aggregate capacity levels.

---

## Step 3c: Run Revision Analyses

These analyses address reviewer concerns: spatial weight sensitivity, FDR-corrected LISA, period-specific Moran's I, spatial regression, Getis-Ord Gi*, match quality, and POI buffer sensitivity.

### Running the Analysis

```bash
# Interactive session (recommended — allows monitoring)
srun --time=06:00:00 --mem=48G --cpus-per-task=4 --pty bash
source venv/bin/activate

python revision_analyses.py
```

### Additional Dependencies

```bash
pip install spreg>=1.4.0 statsmodels>=0.14.0
```

### Expected Output

```
analysis_results/morans_i_sensitivity.csv      # Moran's I with KNN k=4,8,12 + distance bands
analysis_results/lisa_fdr_corrected.csv         # FDR-corrected LISA results
analysis_results/morans_i_by_period.csv         # Period-specific Moran's I (8 periods x 3 cities)
analysis_results/spatial_regression_results.csv # OLS, Spatial Lag, Spatial Error models
analysis_results/getis_ord_results.csv          # Gi* hot/cold spot counts
analysis_results/match_quality.csv              # HERE-OSMnx match distance distribution
analysis_results/poi_network_distance_sensitivity.csv     # POI density at 200m, 400m, 800m, 1200m
```

### Expected Runtime
| Analysis | Estimated Time |
|----------|----------------|
| Weight sensitivity | 5-10 min |
| FDR LISA | 5-10 min |
| Period Moran's I | 10-15 min |
| Spatial regression | 30-60 min (network download) |
| Getis-Ord Gi* | 5-10 min |
| Match quality | 30-60 min (network download) |
| POI network-distance sensitivity | 30-60 min (walk network + POI download) |
| **Total** | **~2-3 hours** |

### Using Results to Update Manuscript

After obtaining the CSV files, update the placeholder tables in `paper/manuscript.md`:
- Table 7a: Spatial weight sensitivity → `morans_i_sensitivity.csv`
- Table 7b: Period-specific Moran's I → `morans_i_by_period.csv`
- Table 8a: FDR-corrected LISA → `lisa_fdr_corrected.csv`
- Table 8b: Getis-Ord Gi* → `getis_ord_results.csv`
- Table 10-mq: Match quality → `match_quality.csv`
- Table 10e-reg: Spatial regression → `spatial_regression_results.csv`

---

## Step 4: Transfer Results Back

```bash
# From HPC to local
scp username@hpc.server.edu:~/traffic-analyses/analysis_results/centrality_correlations.csv ./analysis_results/
```

Or commit and push from HPC:
```bash
git add analysis_results/centrality_correlations.csv
git commit -m "Add centrality-congestion correlation results from HPC"
git push
```

---

## Step 5: Update Manuscript with All Results

After obtaining `centrality_correlations.csv`, run the manuscript update script:

```bash
# On local machine
python update_manuscript.py
```

This will:
1. Read all CSV results from `analysis_results/`
2. Update tables in `paper/manuscript.md`:
   - Table 7: Moran's I spatial autocorrelation
   - Table 8: LISA cluster counts
   - Table 9: ANOVA results
   - Table 10: Centrality-congestion correlations
3. Remove all TODO comments
4. Generate final figures

---

## Analysis Results Interpretation

### Global Moran's I (Spatial Autocorrelation)
| Moran's I | Interpretation |
|-----------|----------------|
| I ≈ 0 | Random spatial pattern |
| I > 0, p < 0.05 | Significant positive autocorrelation (clustering) |
| I < 0, p < 0.05 | Significant negative autocorrelation (dispersion) |

**Current Results:** Moran's I values are close to 0 with p > 0.05, indicating **no significant global spatial autocorrelation**. This means congestion is not uniformly clustered across the entire network, though local clusters exist (see LISA).

### LISA Clusters
| Cluster | Meaning |
|---------|---------|
| HH (High-High) | Hotspot: High congestion surrounded by high congestion |
| LL (Low-Low) | Coldspot: Low congestion surrounded by low congestion |
| HL (High-Low) | Outlier: High congestion surrounded by low congestion |
| LH (Low-High) | Outlier: Low congestion surrounded by high congestion |
| NS | Not statistically significant |

### ANOVA Results
- **F-statistic**: Large values indicate significant differences between time periods
- **p-value**: p < 0.05 confirms statistically significant temporal variation
- **Significant pairs**: Number of period pairs with significant differences (max 28 for 8 periods)

### Centrality-Congestion Correlations
| Correlation | Interpretation |
|-------------|----------------|
| r > 0 | Higher betweenness → higher congestion (expected) |
| r < 0 | Higher betweenness → lower congestion (unexpected) |
| \|r\| < 0.3 | Weak correlation |
| 0.3 ≤ \|r\| < 0.5 | Moderate correlation |
| \|r\| ≥ 0.5 | Strong correlation |

---

## Troubleshooting

### OSMnx Download Fails
```bash
# Set cache directory
export OSMNX_CACHE_FOLDER=/scratch/$USER/osmnx_cache

# Or disable cache if storage is limited
python -c "import osmnx as ox; ox.settings.use_cache = False"
```

### Memory Error on Large Network
```bash
# Request more memory
#SBATCH --mem=64G

# Or use sampling in the script (already implemented for networks > 5000 nodes)
```

### GDAL/PROJ Issues
```bash
# Check GDAL installation
gdalinfo --version

# Set environment variables if needed
export GDAL_DATA=/path/to/gdal/data
export PROJ_LIB=/path/to/proj/data
```

---

## File Structure After Completion

```
traffic-analyses/
├── paper/
│   └── manuscript.md              # Updated with all results
├── analysis_results/
│   ├── morans_i_results.csv       # ✅ Global Moran's I
│   ├── lisa_results.csv           # ✅ LISA clusters
│   ├── anova_results.csv          # ✅ ANOVA + Tukey
│   ├── centrality_correlations.csv       # 🔄 From HPC
│   ├── bottleneck_analysis_results.csv   # 🔄 From HPC
│   ├── morans_i_sensitivity.csv          # 🔄 From HPC (revision)
│   ├── lisa_fdr_corrected.csv            # 🔄 From HPC (revision)
│   ├── morans_i_by_period.csv            # 🔄 From HPC (revision)
│   ├── spatial_regression_results.csv    # 🔄 From HPC (revision)
│   ├── getis_ord_results.csv             # 🔄 From HPC (revision)
│   ├── match_quality.csv                 # 🔄 From HPC (revision)
│   ├── poi_buffer_sensitivity.csv        # 🔄 From HPC (revision)
│   └── advanced_analysis_results.txt
├── figures/
│   ├── smg_lisa_clusters.png      # ✅ LISA maps
│   ├── bdg_lisa_clusters.png
│   ├── jkt_lisa_clusters.png
│   ├── bottleneck_capacity_comparison.png  # 🔄 From HPC
│   ├── capacity_congestion_scatter.png     # 🔄 From HPC
│   ├── capacity_drop_spatial_analysis.png  # 🔄 From HPC
│   └── ... (other figures)
└── HPC_WORKFLOW.md                # This document
```

---

## Next Steps After HPC Analysis

1. **Review centrality correlation results** - Check if correlations are significant
2. **Update manuscript Table 10** - Fill in actual values
3. **Revise Discussion section** - Interpret findings in context
4. **Remove all TODO comments** - Final cleanup
5. **Generate publication-ready figures** - Ensure consistent styling
6. **Proofread methodology** - Ensure methods match actual analyses

---

## Contact

For questions about this workflow, refer to:
- `CLAUDE.md` - Project overview and architecture
- `README.md` - General repository documentation
- Analysis scripts contain detailed docstrings
