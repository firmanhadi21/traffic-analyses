#!/bin/bash
#SBATCH --job-name=traffic_centrality
#SBATCH --output=centrality_%j.out
#SBATCH --error=centrality_%j.err
#SBATCH --time=04:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=4

# Load Python module (adjust for your HPC)
# module load python/3.11
# module load gdal

# Activate virtual environment (if using)
# source venv/bin/activate

# Install dependencies (first time only)
# pip install -r requirements_hpc.txt

echo "Starting centrality analysis..."
echo "Date: $(date)"

# Run the analysis
python compute_centrality_correlations.py

echo "Analysis complete!"
echo "Date: $(date)"
