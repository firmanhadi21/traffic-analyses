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
├── compute_centrality_correlations.py   # Main script to run
├── advanced_spatial_analysis.py         # Already completed analyses
├── requirements_hpc.txt                 # Python dependencies
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
│   ├── centrality_correlations.csv # 🔄 From HPC
│   └── advanced_analysis_results.txt
├── figures/
│   ├── smg_lisa_clusters.png      # ✅ LISA maps
│   ├── bdg_lisa_clusters.png
│   ├── jkt_lisa_clusters.png
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
