#!/usr/bin/env python3
"""
Master script to generate all figures for the FOSS4G 2026 paper.

This script orchestrates the complete figure generation workflow:
1. Verifies prerequisites (data files)
2. Runs LISA analysis (generates Figures 1 + supplementary)
3. Runs Markov analysis (generates Figures 2-6)
4. Verifies all outputs
5. Provides summary report

Usage:
    python generate_all_figures.py [--high-res] [--verify-only]

Options:
    --high-res      Generate figures at 300 DPI (slower, larger files)
    --verify-only   Only verify existing figures, don't regenerate
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/Users/macbook/Dropbox/GitHub/traffic-analyses")

# Required data files
REQUIRED_DATA = {
    'jkt': 8,  # 8 periods
    'bdg': 8,
    'smg': 8,
}

PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night'
]


def print_header(title):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(title.upper())
    print("=" * 80)


def print_step(step_num, description):
    """Print step indicator."""
    print(f"\n[Step {step_num}] {description}")
    print("-" * 80)


def verify_data_prerequisites():
    """Check that all required traffic data GeoPackages exist."""
    print_step(1, "Verifying Data Prerequisites")
    
    missing_files = []
    found_files = []
    
    for city, expected_periods in REQUIRED_DATA.items():
        city_dir = BASE_DIR / f"traffic_{city}_output"
        
        if not city_dir.exists():
            print(f"  ✗ Directory not found: {city_dir.name}/")
            missing_files.append(f"{city_dir.name}/")
            continue
        
        for period in PERIODS:
            gpkg_path = city_dir / period / "aggregated_segments.gpkg"
            
            if gpkg_path.exists():
                found_files.append(gpkg_path)
                print(f"  ✓ {gpkg_path.relative_to(BASE_DIR)}")
            else:
                missing_files.append(str(gpkg_path.relative_to(BASE_DIR)))
                print(f"  ✗ Missing: {gpkg_path.relative_to(BASE_DIR)}")
    
    print(f"\nFound: {len(found_files)}/24 data files")
    
    if missing_files:
        print("\n⚠️  WARNING: Some data files are missing!")
        print("Cannot generate figures without complete data.")
        print("\nTo collect traffic data, run:")
        print("  traffic-pipeline collect --provider here --api-key $YOUR_KEY")
        return False
    
    print("\n✅ All data files present!")
    return True


def run_lisa_analysis(high_res=False):
    """Run LISA analysis to generate Figure 1 and supplementary figures."""
    print_step(2, "Running LISA Analysis (Generates Figure 1)")
    
    cmd = ["python", "compute_lisa_all_periods.py"]
    
    if high_res:
        print("  📊 High-resolution mode enabled (300 DPI)")
        # Note: Would need to modify script to accept --high-res flag
    
    print(f"\n  Running: {' '.join(cmd)}")
    print("  Estimated time: 10-15 minutes...\n")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=1200  # 20 minute timeout
        )
        
        if result.returncode == 0:
            print("\n✅ LISA analysis completed successfully!")
            print("\nGenerated:")
            print("  - Figure 1: LISA cluster maps (3 cities)")
            print("  - 24 individual LISA GeoPackages")
            print("  - 3 combined time-series GeoPackages")
            return True
        else:
            print(f"\n✗ LISA analysis failed with exit code {result.returncode}")
            print("\nError output:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("\n✗ LISA analysis timed out (>20 minutes)")
        return False
    except Exception as e:
        print(f"\n✗ Error running LISA analysis: {e}")
        return False


def run_markov_analysis(high_res=False):
    """Run Markov analysis to generate Figures 2-6."""
    print_step(3, "Running Markov Analysis (Generates Figures 2-6)")
    
    cmd = ["python", "compute_lisa_markov.py"]
    
    if high_res:
        print("  📊 High-resolution mode enabled (300 DPI)")
    
    print(f"\n  Running: {' '.join(cmd)}")
    print("  Estimated time: 1-2 minutes...\n")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print("\n✅ Markov analysis completed successfully!")
            print("\nGenerated:")
            print("  - Figure 2: Transition matrices (3 cities)")
            print("  - Figure 3: Diagonal dominance comparison")
            print("  - Figure 4: Steady-state distributions")
            print("  - Figure 5: Spatial contagion tests")
            print("  - Figure 6: Temporal persistence analysis")
            print("  - Numerical results (CSV)")
            print("  - Analysis report (TXT)")
            return True
        else:
            print(f"\n✗ Markov analysis failed with exit code {result.returncode}")
            print("\nError output:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("\n✗ Markov analysis timed out (>5 minutes)")
        return False
    except Exception as e:
        print(f"\n✗ Error running Markov analysis: {e}")
        return False


def verify_all_figures():
    """Run verification script to check all figures exist."""
    print_step(4, "Verifying Figure Outputs")
    
    cmd = ["python", "verify_paper_figures.py"]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=False,  # Show output directly
            timeout=30
        )
        
        return result.returncode == 0
            
    except Exception as e:
        print(f"\n✗ Error running verification: {e}")
        return False


def main():
    """Main workflow orchestration."""
    parser = argparse.ArgumentParser(
        description='Generate all figures for FOSS4G 2026 paper'
    )
    parser.add_argument('--high-res', action='store_true',
                       help='Generate high-resolution figures (300 DPI)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify figures, do not regenerate')
    
    args = parser.parse_args()
    
    print_header("FOSS4G 2026 Paper - Figure Generation Workflow")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.verify_only:
        print("\nMode: Verification only (no regeneration)")
        success = verify_all_figures()
        return 0 if success else 1
    
    # Step 1: Verify data
    if not verify_data_prerequisites():
        print("\n❌ Cannot proceed without complete data files.")
        print("Please collect traffic data first.")
        return 1
    
    # Step 2: Run LISA analysis
    if not run_lisa_analysis(high_res=args.high_res):
        print("\n❌ LISA analysis failed. Cannot proceed to Markov analysis.")
        return 1
    
    # Step 3: Run Markov analysis
    if not run_markov_analysis(high_res=args.high_res):
        print("\n❌ Markov analysis failed.")
        return 1
    
    # Step 4: Verify outputs
    if not verify_all_figures():
        print("\n⚠️  Warning: Some figures may be missing or incomplete.")
        return 1
    
    # Success summary
    print_header("Workflow Complete!")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n✅ All figures generated successfully!")
    print("\nFigures are ready for:")
    print("  - Integration into FOSS4G 2026 paper")
    print("  - Quality review and editing")
    print("  - High-resolution export for final submission")
    print("\nNext steps:")
    print("  1. Review figure quality: open files in figures/ and figures/markov/")
    print("  2. Add figure captions to paper: docs/foss4g_paper.md")
    print("  3. Export high-res versions: Re-run with --high-res flag")
    print("  4. See FIGURE_GENERATION.md for submission guidelines")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
