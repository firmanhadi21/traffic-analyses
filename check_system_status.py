#!/usr/bin/env python3
"""
System status checker for OSM-based traffic aggregation.
Checks dependencies, data files, and provides next steps guidance.
"""

import sys
import subprocess
from pathlib import Path
import json

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def check_dependencies():
    """Check if required Python packages are installed."""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Checking Dependencies{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    required_packages = {
        'geopandas': 'geopandas',
        'osmnx': 'osmnx',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'shapely': 'shapely',
        'tqdm': 'tqdm',
        'pytz': 'pytz',
        'matplotlib': 'matplotlib',
        'seaborn': 'seaborn'
    }

    all_installed = True
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"  {GREEN}✓{NC} {package_name}")
        except ImportError:
            print(f"  {RED}✗{NC} {package_name} (missing)")
            all_installed = False

    if not all_installed:
        print(f"\n{YELLOW}Install missing packages with:{NC}")
        print(f"  pip install -r requirements.txt")
        return False
    else:
        print(f"\n{GREEN}All dependencies installed!{NC}")
        return True


def check_traffic_data():
    """Check if traffic data directories exist and contain files."""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Checking Traffic Data{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    cities = {
        'smg': 'traffic_data_smg',
        'bdg': 'traffic_data_bdg',
        'jkt': 'traffic_data_jkt'
    }

    data_status = {}
    for city_code, dir_name in cities.items():
        data_dir = Path(dir_name)
        if data_dir.exists():
            # Count GPKG files
            gpkg_files = list(data_dir.glob('*.gpkg'))
            data_status[city_code] = len(gpkg_files)
            print(f"  {GREEN}✓{NC} {city_code.upper()}: {len(gpkg_files)} files in {dir_name}/")
        else:
            data_status[city_code] = 0
            print(f"  {RED}✗{NC} {city_code.upper()}: {dir_name}/ not found")

    total_files = sum(data_status.values())
    if total_files == 0:
        print(f"\n{RED}No traffic data found!{NC}")
        print(f"Ensure traffic_collector.R has been run to collect data.")
        return False
    else:
        print(f"\n{GREEN}Total traffic files: {total_files}{NC}")
        return True


def check_osm_networks():
    """Check if OSM reference networks exist."""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Checking OSM Reference Networks{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    osm_dir = Path('osm_reference')
    if not osm_dir.exists():
        print(f"  {YELLOW}⊘{NC} osm_reference/ directory not found (will be created)")
        return False

    cities = ['smg', 'bdg', 'jkt']
    networks_found = 0

    for city in cities:
        # Find any OSM reference file for this city
        ref_files = list(osm_dir.glob(f'{city}_osm_reference_*.gpkg'))
        if ref_files:
            latest_file = max(ref_files, key=lambda p: p.stat().st_mtime)
            file_size_mb = latest_file.stat().st_size / 1024 / 1024
            print(f"  {GREEN}✓{NC} {city.upper()}: {latest_file.name} ({file_size_mb:.1f} MB)")
            networks_found += 1
        else:
            print(f"  {YELLOW}⊘{NC} {city.upper()}: No OSM reference found")

    if networks_found == 0:
        print(f"\n{YELLOW}No OSM networks found. Run:{NC}")
        print(f"  python osm_network_builder.py --all --date $(date +%Y%m%d)")
        return False
    elif networks_found < 3:
        print(f"\n{YELLOW}Some OSM networks missing. Download with:{NC}")
        print(f"  python osm_network_builder.py --all --date $(date +%Y%m%d)")
        return True
    else:
        print(f"\n{GREEN}All OSM networks found!{NC}")
        return True


def check_mappings():
    """Check if HERE→OSM mapping tables exist."""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Checking HERE→OSM Mappings{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    osm_dir = Path('osm_reference')
    if not osm_dir.exists():
        print(f"  {YELLOW}⊘{NC} osm_reference/ directory not found")
        return False

    cities = ['smg', 'bdg', 'jkt']
    mappings_found = 0

    for city in cities:
        # Find any mapping file for this city
        mapping_files = list(osm_dir.glob(f'{city}_here_to_osm_mapping_*.csv'))
        if mapping_files:
            latest_file = max(mapping_files, key=lambda p: p.stat().st_mtime)
            file_size_kb = latest_file.stat().st_size / 1024

            # Try to read diagnostics
            diag_files = list(Path('aggregated_output').glob(f'{city}/diagnostics/{city}_matching_diagnostics_*.json'))
            if diag_files:
                latest_diag = max(diag_files, key=lambda p: p.stat().st_mtime)
                try:
                    with open(latest_diag, 'r') as f:
                        diag = json.load(f)
                    match_rate = diag.get('overall_osm_match_rate', 0)
                    print(f"  {GREEN}✓{NC} {city.upper()}: {latest_file.name} ({file_size_kb:.1f} KB, {match_rate:.1%} match rate)")
                except:
                    print(f"  {GREEN}✓{NC} {city.upper()}: {latest_file.name} ({file_size_kb:.1f} KB)")
            else:
                print(f"  {GREEN}✓{NC} {city.upper()}: {latest_file.name} ({file_size_kb:.1f} KB)")
            mappings_found += 1
        else:
            print(f"  {YELLOW}⊘{NC} {city.upper()}: No mapping found")

    if mappings_found == 0:
        print(f"\n{YELLOW}No mappings found. Create with:{NC}")
        print(f"  python create_here_osm_mapping.py --all --date $(date +%Y%m%d)")
        return False
    elif mappings_found < 3:
        print(f"\n{YELLOW}Some mappings missing. Create with:{NC}")
        print(f"  python create_here_osm_mapping.py --all --date $(date +%Y%m%d)")
        return True
    else:
        print(f"\n{GREEN}All mappings found!{NC}")
        return True


def check_aggregated_outputs():
    """Check if any aggregated outputs exist."""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Checking Aggregated Outputs{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    output_dir = Path('aggregated_output')
    if not output_dir.exists():
        print(f"  {YELLOW}⊘{NC} aggregated_output/ directory not found (will be created)")
        return False

    cities = ['smg', 'bdg', 'jkt']
    outputs_found = 0

    for city in cities:
        osm_output_dir = output_dir / city / 'osm_based'
        if osm_output_dir.exists():
            output_files = list(osm_output_dir.glob('*.gpkg'))
            if output_files:
                total_size_mb = sum(f.stat().st_size for f in output_files) / 1024 / 1024
                print(f"  {GREEN}✓{NC} {city.upper()}: {len(output_files)} aggregated files ({total_size_mb:.1f} MB)")
                outputs_found += 1
            else:
                print(f"  {YELLOW}⊘{NC} {city.upper()}: No aggregated outputs")
        else:
            print(f"  {YELLOW}⊘{NC} {city.upper()}: No osm_based/ directory")

    if outputs_found == 0:
        print(f"\n{YELLOW}No aggregated outputs found. Run:{NC}")
        print(f"  ./quickstart_pipeline.sh --city smg")
        return False
    else:
        print(f"\n{GREEN}Found aggregated outputs for {outputs_found} city/cities!{NC}")
        return True


def provide_next_steps(dep_ok, data_ok, osm_ok, mapping_ok, output_ok):
    """Provide guidance on next steps based on system status."""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Next Steps{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    if not dep_ok:
        print(f"{YELLOW}1. Install dependencies:{NC}")
        print(f"   pip install -r requirements.txt\n")
        return

    if not data_ok:
        print(f"{RED}No traffic data found!{NC}")
        print(f"Please run the traffic collector to gather data first:")
        print(f"  ./traffic_collector.sh\n")
        return

    if not osm_ok:
        print(f"{YELLOW}1. Download OSM networks:{NC}")
        print(f"   python osm_network_builder.py --all --date $(date +%Y%m%d)")
        print(f"   (Takes ~5 minutes per city)\n")
        return

    if not mapping_ok:
        print(f"{YELLOW}2. Create HERE→OSM mappings:{NC}")
        print(f"   python create_here_osm_mapping.py --all --date $(date +%Y%m%d)")
        print(f"   (Takes ~10 minutes per city)\n")
        return

    if not output_ok:
        print(f"{GREEN}System ready for aggregation!{NC}\n")
        print(f"{YELLOW}3. Run aggregation pipeline:{NC}")
        print(f"   # Quick test (recommended first)")
        print(f"   ./test_small_sample.sh\n")
        print(f"   # Full pipeline for Semarang")
        print(f"   ./quickstart_pipeline.sh --city smg\n")
        print(f"   # Custom aggregation")
        print(f"   python aggregate_traffic_with_osm.py \\")
        print(f"     --city smg \\")
        print(f"     --metric jam_factor \\")
        print(f"     --time-period \"morning_peak:6-9\" \\")
        print(f"     --temporal-grouping weekly \\")
        print(f"     --start-date 2025-01-01 \\")
        print(f"     --end-date 2025-12-31 \\")
        print(f"     --mapping-date $(date +%Y%m%d)\n")
    else:
        print(f"{GREEN}System fully operational!{NC}\n")
        print(f"You have aggregated outputs. Options:\n")
        print(f"  • Visualize in QGIS: Open .gpkg files from aggregated_output/")
        print(f"  • Run new aggregations with different parameters")
        print(f"  • Validate results: python compare_legacy_vs_osm.py ...")
        print(f"  • See README_OSM_AGGREGATION.md for analysis workflows\n")


def main():
    """Main entry point."""
    print(f"{BLUE}{'='*60}{NC}")
    print(f"{BLUE}OSM-Based Traffic Aggregation - System Status{NC}")
    print(f"{BLUE}{'='*60}{NC}")

    # Run all checks
    dep_ok = check_dependencies()
    data_ok = check_traffic_data()
    osm_ok = check_osm_networks()
    mapping_ok = check_mappings()
    output_ok = check_aggregated_outputs()

    # Provide guidance
    provide_next_steps(dep_ok, data_ok, osm_ok, mapping_ok, output_ok)

    # Overall status
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Overall Status{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

    checks = [
        ("Dependencies", dep_ok),
        ("Traffic Data", data_ok),
        ("OSM Networks", osm_ok),
        ("Mappings", mapping_ok),
        ("Outputs", output_ok)
    ]

    for name, status in checks:
        status_str = f"{GREEN}✓{NC}" if status else f"{RED}✗{NC}"
        print(f"  {status_str} {name}")

    all_ok = all(status for _, status in checks)
    if all_ok:
        print(f"\n{GREEN}All systems operational!{NC}\n")
    else:
        incomplete = sum(1 for _, status in checks if not status)
        print(f"\n{YELLOW}{incomplete} of {len(checks)} components need setup.{NC}\n")


if __name__ == '__main__':
    main()
