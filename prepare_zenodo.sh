#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# prepare_zenodo.sh — Bundle aggregated data + analysis results for Zenodo
#
# Creates  zenodo_data.zip  containing the 24 GeoPackages (8 periods × 3
# cities), the analysis_results CSVs, and a DATA_README.md.
#
# Usage:
#   chmod +x prepare_zenodo.sh
#   ./prepare_zenodo.sh
# ---------------------------------------------------------------------------
set -euo pipefail

BUNDLE_DIR="zenodo_data"
ZIP_NAME="zenodo_data.zip"

echo "=== Preparing Zenodo data bundle ==="

# Clean previous bundle
rm -rf "$BUNDLE_DIR" "$ZIP_NAME"
mkdir -p "$BUNDLE_DIR"

# --- Aggregated GeoPackages ---
for city_dir in traffic_smg_output traffic_bdg_output traffic_jkt_output; do
    if [ -d "$city_dir" ]; then
        mkdir -p "$BUNDLE_DIR/$city_dir"
        cp "$city_dir"/*.gpkg "$BUNDLE_DIR/$city_dir/"
        echo "  Copied $(ls "$city_dir"/*.gpkg | wc -l | tr -d ' ') files from $city_dir"
    else
        echo "  WARNING: $city_dir not found, skipping"
    fi
done

# --- Analysis results ---
if [ -d "analysis_results" ]; then
    mkdir -p "$BUNDLE_DIR/analysis_results"
    cp analysis_results/*.csv "$BUNDLE_DIR/analysis_results/" 2>/dev/null || true
    cp analysis_results/*.txt "$BUNDLE_DIR/analysis_results/" 2>/dev/null || true
    echo "  Copied analysis_results/"
fi

# --- Data README ---
cp DATA_README.md "$BUNDLE_DIR/"
echo "  Copied DATA_README.md"

# --- Create zip ---
zip -r "$ZIP_NAME" "$BUNDLE_DIR/" -x "*.DS_Store"

SIZE=$(du -sh "$ZIP_NAME" | cut -f1)
echo ""
echo "=== Done ==="
echo "Bundle:  $ZIP_NAME  ($SIZE)"
echo "Upload this file to https://zenodo.org/deposit/new"
echo ""
echo "Suggested Zenodo metadata:"
echo "  Title:       Traffic Congestion Dataset: Semarang, Bandung, Jakarta (2025-2026)"
echo "  Type:        Dataset"
echo "  License:     MIT"
echo "  Keywords:    traffic congestion, spatiotemporal, HERE API, Indonesia, GeoPackage"
echo "  Related ID:  https://github.com/firmanhadi21/traffic-analyses (isSupplementTo)"
