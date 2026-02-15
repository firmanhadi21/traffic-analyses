#!/bin/bash
#SBATCH --job-name=traffic_analysis
#SBATCH --output=analysis_%j.out
#SBATCH --error=analysis_%j.err
#SBATCH --time=06:00:00
#SBATCH --mem=48G
#SBATCH --cpus-per-task=4

# Load Python module (adjust for your HPC)
# module load python/3.11
# module load gdal

# Activate virtual environment (if using)
# source venv/bin/activate

# Install dependencies (first time only)
# pip install -r requirements_hpc.txt
# pip install -r requirements_revision.txt

echo "Starting analyses..."
echo "Date: $(date)"

# Run centrality analysis
echo "--- Centrality Analysis ---"
python compute_centrality_correlations.py

# Run revision analyses (spatial weight sensitivity, FDR LISA, spatial regression, etc.)
echo "--- Revision Analyses ---"
python revision_analyses.py

echo "All analyses complete!"
echo "Date: $(date)"
