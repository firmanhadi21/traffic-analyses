#!/bin/bash
# Test script for validating the OSM aggregation system with a small sample
# Uses Semarang data for 1 day (~96 files) as a quick smoke test

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OSM Aggregation System - Smoke Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "This test uses Semarang data for 1 day to validate the system."
echo "Expected runtime: ~5 minutes"
echo ""

# Configuration
CITY="smg"
REFERENCE_DATE=$(date +%Y%m%d)
TEST_DATE="2025-01-15"  # Use a single day for testing

echo -e "${GREEN}Test configuration:${NC}"
echo "  City: Semarang (smg)"
echo "  Reference date: $REFERENCE_DATE"
echo "  Test date: $TEST_DATE (1 day sample)"
echo ""

# Check if traffic data exists
TRAFFIC_DIR="traffic_data_smg"
if [[ ! -d "$TRAFFIC_DIR" ]]; then
    echo -e "${RED}Error: Traffic data directory not found: $TRAFFIC_DIR${NC}"
    echo "Please ensure traffic data has been collected."
    exit 1
fi

# Count files for test date
FILE_COUNT=$(ls -1 "$TRAFFIC_DIR"/semarang_traffic_20250115_*.gpkg 2>/dev/null | wc -l)
if [[ $FILE_COUNT -eq 0 ]]; then
    echo -e "${YELLOW}Warning: No files found for test date $TEST_DATE${NC}"
    echo "Using any available date for testing..."
    # Find any available date
    FIRST_FILE=$(ls -1 "$TRAFFIC_DIR"/semarang_traffic_*.gpkg | head -1)
    if [[ -z "$FIRST_FILE" ]]; then
        echo -e "${RED}Error: No traffic files found in $TRAFFIC_DIR${NC}"
        exit 1
    fi
    # Extract date from filename
    TEST_DATE=$(basename "$FIRST_FILE" | grep -oP '\d{8}' | head -1)
    TEST_DATE="${TEST_DATE:0:4}-${TEST_DATE:4:2}-${TEST_DATE:6:2}"
    FILE_COUNT=$(ls -1 "$TRAFFIC_DIR"/semarang_traffic_${TEST_DATE//-/}_*.gpkg 2>/dev/null | wc -l)
fi

echo "  Files for test: $FILE_COUNT"
echo ""

# Confirm
read -p "Proceed with test? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Test 1: Check dependencies
echo ""
echo -e "${BLUE}Test 1: Checking dependencies...${NC}"
python -c "
import sys
try:
    import geopandas
    import osmnx
    import pandas
    import numpy
    import shapely
    import tqdm
    import pytz
    print('✓ All required packages found')
except ImportError as e:
    print(f'✗ Missing package: {e}')
    print('\nInstall dependencies with:')
    print('  pip install -r requirements.txt')
    sys.exit(1)
"

# Test 2: Download OSM network
echo ""
echo -e "${BLUE}Test 2: Downloading OSM network...${NC}"
python osm_network_builder.py --city "$CITY" --date "$REFERENCE_DATE"
if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ OSM network download successful${NC}"
else
    echo -e "${RED}✗ OSM network download failed${NC}"
    exit 1
fi

# Test 3: Create mapping
echo ""
echo -e "${BLUE}Test 3: Creating HERE→OSM mapping...${NC}"
python create_here_osm_mapping.py --city "$CITY" --date "$REFERENCE_DATE"
if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Mapping creation successful${NC}"
else
    echo -e "${RED}✗ Mapping creation failed${NC}"
    exit 1
fi

# Test 4: Check mapping quality
echo ""
echo -e "${BLUE}Test 4: Checking mapping quality...${NC}"
python -c "
import json
import sys

diagnostics_file = 'aggregated_output/smg/diagnostics/smg_matching_diagnostics_${REFERENCE_DATE}.json'
with open(diagnostics_file, 'r') as f:
    diag = json.load(f)

print(f\"  Total segments: {diag['total_segments']}\")
print(f\"  OSM match rate: {diag['overall_osm_match_rate']:.1%}\")
print(f\"  Synthetic IDs: {diag['synthetic_ids']} ({diag['synthetic_rate']:.1%})\")

if diag['overall_osm_match_rate'] >= 0.95:
    print('✓ Match rate meets target (≥95%)')
else:
    print(f\"✗ Match rate below target: {diag['overall_osm_match_rate']:.1%}\")
    sys.exit(1)

if diag['nearest_neighbor_matched'] > 0:
    if diag['nearest_neighbor_mean_distance_m'] <= 20:
        print(f\"✓ Mean NN distance meets target: {diag['nearest_neighbor_mean_distance_m']:.1f}m (≤20m)\")
    else:
        print(f\"⚠ Mean NN distance above target: {diag['nearest_neighbor_mean_distance_m']:.1f}m\")
"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Mapping quality check passed${NC}"
else
    echo -e "${RED}✗ Mapping quality check failed${NC}"
    exit 1
fi

# Test 5: Aggregate sample data
echo ""
echo -e "${BLUE}Test 5: Aggregating sample data (1 day)...${NC}"
python aggregate_traffic_with_osm.py \
    --city "$CITY" \
    --metric jam_factor \
    --time-period "morning_peak:6-9" \
    --temporal-grouping daily \
    --start-date "$TEST_DATE" \
    --end-date "$TEST_DATE" \
    --mapping-date "$REFERENCE_DATE"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Aggregation successful${NC}"
else
    echo -e "${RED}✗ Aggregation failed${NC}"
    exit 1
fi

# Test 6: Validate output
echo ""
echo -e "${BLUE}Test 6: Validating output...${NC}"
python -c "
import geopandas as gpd
import sys

test_date_compact = '${TEST_DATE}'.replace('-', '')
output_file = f'aggregated_output/smg/osm_based/smg_morning_peak_daily_jam_factor_{test_date_compact}_{test_date_compact}.gpkg'

try:
    gdf = gpd.read_file(output_file)
    print(f'  Rows: {len(gdf)}')
    print(f'  Columns: {list(gdf.columns)}')
    print(f'  Unique segments: {gdf[\"osm_composite_id\"].nunique()}')

    # Check required columns
    required_cols = ['osm_composite_id', 'temporal_group', 'jam_factor_mean', 'jam_factor_std',
                     'jam_factor_count', 'jam_factor_min', 'jam_factor_max', 'geometry']
    missing_cols = [col for col in required_cols if col not in gdf.columns]

    if missing_cols:
        print(f'✗ Missing columns: {missing_cols}')
        sys.exit(1)

    print('✓ All required columns present')

    # Check for data
    if len(gdf) == 0:
        print('✗ No data in output')
        sys.exit(1)

    print('✓ Output contains data')

    # Check statistics
    print(f'\\nData summary:')
    print(f'  Mean jam_factor: {gdf[\"jam_factor_mean\"].mean():.2f}')
    print(f'  Std jam_factor: {gdf[\"jam_factor_mean\"].std():.2f}')
    print(f'  Mean observations per segment: {gdf[\"jam_factor_count\"].mean():.1f}')

except Exception as e:
    print(f'✗ Error loading output: {e}')
    sys.exit(1)
"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Output validation passed${NC}"
else
    echo -e "${RED}✗ Output validation failed${NC}"
    exit 1
fi

# Final summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}All Tests Passed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}The OSM aggregation system is working correctly.${NC}"
echo ""
echo "Next steps:"
echo "  1. Run full aggregation with: ./quickstart_pipeline.sh --city smg"
echo "  2. Try different parameters (time periods, temporal groupings)"
echo "  3. Process other cities (bdg, jkt)"
echo ""
echo "Generated test files:"
echo "  - osm_reference/smg_osm_reference_${REFERENCE_DATE}.gpkg"
echo "  - osm_reference/smg_here_to_osm_mapping_${REFERENCE_DATE}.csv"
echo "  - aggregated_output/smg/osm_based/smg_morning_peak_daily_jam_factor_*.gpkg"
echo ""
