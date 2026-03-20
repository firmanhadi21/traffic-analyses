#!/bin/bash
# Quick start script for OSM-based traffic aggregation pipeline
# This script automates the entire workflow for a single city

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CITY=""
REFERENCE_DATE=$(date +%Y%m%d)
METRIC="jam_factor"
TIME_PERIOD="morning_peak:6-9"
TEMPORAL_GROUPING="weekly"
START_DATE="2025-01-01"
END_DATE="2025-12-31"
SKIP_OSM=false
SKIP_MAPPING=false
VALIDATE=true

# Usage function
usage() {
    cat << EOF
Usage: $0 --city CITY [OPTIONS]

Required:
  --city CITY              City code (smg, bdg, or jkt)

Optional:
  --reference-date DATE    Reference date for OSM/mapping (YYYYMMDD, default: today)
  --metric METRIC          Traffic metric (jam_factor, speed, free_flow, default: jam_factor)
  --time-period PERIOD     Time period (format: "name:start-end", default: "morning_peak:6-9")
  --temporal-grouping GRP  Grouping (daily, weekly, monthly, all, default: weekly)
  --start-date DATE        Start date for aggregation (YYYY-MM-DD, default: 2025-01-01)
  --end-date DATE          End date for aggregation (YYYY-MM-DD, default: 2025-12-31)
  --skip-osm               Skip OSM network download (use existing)
  --skip-mapping           Skip mapping creation (use existing)
  --no-validate            Skip validation step
  -h, --help               Show this help message

Examples:
  # Full pipeline for Semarang morning peak
  $0 --city smg

  # Jakarta evening peak with monthly aggregation
  $0 --city jkt --time-period "evening_peak:16-19" --temporal-grouping monthly

  # Use existing OSM and mapping, just re-aggregate
  $0 --city bdg --skip-osm --skip-mapping --time-period "allday:0-24"

EOF
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --city)
            CITY="$2"
            shift 2
            ;;
        --reference-date)
            REFERENCE_DATE="$2"
            shift 2
            ;;
        --metric)
            METRIC="$2"
            shift 2
            ;;
        --time-period)
            TIME_PERIOD="$2"
            shift 2
            ;;
        --temporal-grouping)
            TEMPORAL_GROUPING="$2"
            shift 2
            ;;
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --skip-osm)
            SKIP_OSM=true
            shift
            ;;
        --skip-mapping)
            SKIP_MAPPING=true
            shift
            ;;
        --no-validate)
            VALIDATE=false
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$CITY" ]]; then
    echo -e "${RED}Error: --city is required${NC}"
    usage
fi

if [[ ! "$CITY" =~ ^(smg|bdg|jkt)$ ]]; then
    echo -e "${RED}Error: City must be smg, bdg, or jkt${NC}"
    exit 1
fi

# Extract time period name for output
TIME_PERIOD_NAME=$(echo "$TIME_PERIOD" | cut -d: -f1)

# Print configuration
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OSM-Based Traffic Aggregation Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  City: $CITY"
echo "  Reference date: $REFERENCE_DATE"
echo "  Metric: $METRIC"
echo "  Time period: $TIME_PERIOD"
echo "  Temporal grouping: $TEMPORAL_GROUPING"
echo "  Date range: $START_DATE to $END_DATE"
echo ""
echo -e "${GREEN}Pipeline steps:${NC}"
[[ "$SKIP_OSM" == false ]] && echo "  ✓ Download OSM network" || echo "  ⊘ Skip OSM download"
[[ "$SKIP_MAPPING" == false ]] && echo "  ✓ Create HERE→OSM mapping" || echo "  ⊘ Skip mapping creation"
echo "  ✓ Aggregate traffic data"
[[ "$VALIDATE" == true ]] && echo "  ✓ Validate results" || echo "  ⊘ Skip validation"
echo ""

# Confirm before proceeding
read -p "Proceed with pipeline? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Step 1: Download OSM network
if [[ "$SKIP_OSM" == false ]]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Step 1: Downloading OSM Network${NC}"
    echo -e "${BLUE}========================================${NC}"
    python osm_network_builder.py --city "$CITY" --date "$REFERENCE_DATE"
    echo -e "${GREEN}✓ OSM network download complete${NC}"
else
    echo ""
    echo -e "${YELLOW}⊘ Skipping OSM network download${NC}"
fi

# Step 2: Create mapping
if [[ "$SKIP_MAPPING" == false ]]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Step 2: Creating HERE→OSM Mapping${NC}"
    echo -e "${BLUE}========================================${NC}"
    python create_here_osm_mapping.py --city "$CITY" --date "$REFERENCE_DATE"
    echo -e "${GREEN}✓ Mapping creation complete${NC}"
else
    echo ""
    echo -e "${YELLOW}⊘ Skipping mapping creation${NC}"
fi

# Step 3: Aggregate traffic data
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Step 3: Aggregating Traffic Data${NC}"
echo -e "${BLUE}========================================${NC}"
python aggregate_traffic_with_osm.py \
    --city "$CITY" \
    --metric "$METRIC" \
    --time-period "$TIME_PERIOD" \
    --temporal-grouping "$TEMPORAL_GROUPING" \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --mapping-date "$REFERENCE_DATE"
echo -e "${GREEN}✓ Traffic aggregation complete${NC}"

# Step 4: Validate results
if [[ "$VALIDATE" == true ]]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Step 4: Validating Results${NC}"
    echo -e "${BLUE}========================================${NC}"
    python compare_legacy_vs_osm.py \
        --city "$CITY" \
        --time-period-name "$TIME_PERIOD_NAME" \
        --temporal-grouping "$TEMPORAL_GROUPING" \
        --metric "$METRIC" \
        --start-date "${START_DATE//-/}" \
        --end-date "${END_DATE//-/}"
    echo -e "${GREEN}✓ Validation complete${NC}"
else
    echo ""
    echo -e "${YELLOW}⊘ Skipping validation${NC}"
fi

# Final summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Pipeline Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Output files:${NC}"

# Convert dates to YYYYMMDD format for filename
START_DATE_COMPACT="${START_DATE//-/}"
END_DATE_COMPACT="${END_DATE//-/}"

OUTPUT_FILE="aggregated_output/${CITY}/osm_based/${CITY}_${TIME_PERIOD_NAME}_${TEMPORAL_GROUPING}_${METRIC}_${START_DATE_COMPACT}_${END_DATE_COMPACT}.gpkg"

if [[ -f "$OUTPUT_FILE" ]]; then
    echo "  📊 Aggregated data: $OUTPUT_FILE"
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "     Size: $FILE_SIZE"
fi

DIAGNOSTICS_FILE="aggregated_output/${CITY}/diagnostics/${CITY}_matching_diagnostics_${REFERENCE_DATE}.json"
if [[ -f "$DIAGNOSTICS_FILE" ]]; then
    echo "  📈 Diagnostics: $DIAGNOSTICS_FILE"
fi

PLOT_FILE="aggregated_output/${CITY}/diagnostics/${CITY}_observation_consistency.png"
if [[ -f "$PLOT_FILE" ]]; then
    echo "  📊 Validation plot: $PLOT_FILE"
fi

echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Open the GPKG in QGIS for visualization"
echo "  2. Review diagnostics JSON for match quality"
echo "  3. Check validation plot for observation consistency"
echo ""
echo -e "${BLUE}To run again with different parameters:${NC}"
echo "  $0 --city $CITY --skip-osm --skip-mapping --time-period \"evening_peak:16-19\""
echo ""
