#!/usr/bin/env python3
"""
Verify that all figures required for the FOSS4G 2026 paper exist.

This script checks the existence of all figures referenced in the paper
and provides a summary report with recommendations.
"""

import sys
from pathlib import Path
from datetime import datetime

# Base directory
BASE_DIR = Path("/Users/macbook/Dropbox/GitHub/traffic-analyses")
FIGURES_DIR = BASE_DIR / "figures"

# Required figures for FOSS4G 2026 paper
REQUIRED_FIGURES = {
    "Figure 1: LISA Cluster Maps (Evening Peak)": [
        FIGURES_DIR / "jkt_hotspots_evening_peak.png",
        FIGURES_DIR / "bdg_hotspots_evening_peak.png",
        FIGURES_DIR / "smg_hotspots_evening_peak.png",
    ],
    "Figure 2: Transition Probability Matrices": [
        FIGURES_DIR / "markov" / "jkt_transition_matrix.png",
        FIGURES_DIR / "markov" / "bdg_transition_matrix.png",
        FIGURES_DIR / "markov" / "smg_transition_matrix.png",
    ],
    "Figure 3: Diagonal Dominance Comparison": [
        FIGURES_DIR / "markov" / "diagonal_dominance.png",
    ],
    "Figure 4: Steady-State Distributions": [
        FIGURES_DIR / "markov" / "steady_state_comparison.png",
    ],
    "Figure 5: Spatial Contagion Test Results": [
        FIGURES_DIR / "markov" / "spatial_contagion_test.png",
    ],
    "Figure 6: Temporal Persistence Analysis": [
        FIGURES_DIR / "markov" / "persistence_analysis.png",
    ],
}

# Optional supplementary figures
SUPPLEMENTARY_FIGURES = {
    "LISA Cluster Maps (All Cities)": [
        FIGURES_DIR / "jkt_lisa_clusters.png",
        FIGURES_DIR / "bdg_lisa_clusters.png",
        FIGURES_DIR / "smg_lisa_clusters.png",
    ],
    "LISA Significance Maps": [
        FIGURES_DIR / "jkt_lisa_significance.png",
        FIGURES_DIR / "bdg_lisa_significance.png",
        FIGURES_DIR / "smg_lisa_significance.png",
    ],
    "Moran Scatterplots": [
        FIGURES_DIR / "jkt_moran_scatterplot.png",
        FIGURES_DIR / "bdg_moran_scatterplot.png",
        FIGURES_DIR / "smg_moran_scatterplot.png",
    ],
}


def check_figure_exists(filepath: Path) -> dict:
    """Check if a figure exists and get its properties."""
    exists = filepath.exists()
    info = {
        'exists': exists,
        'path': str(filepath.relative_to(BASE_DIR)),
    }
    
    if exists:
        stat = filepath.stat()
        info['size_kb'] = round(stat.st_size / 1024, 2)
        info['modified'] = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    else:
        info['size_kb'] = 0
        info['modified'] = 'N/A'
    
    return info


def verify_figures():
    """Verify all required and supplementary figures."""
    print("=" * 80)
    print("FOSS4G 2026 PAPER - FIGURE VERIFICATION REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    all_exist = True
    total_required = 0
    total_found = 0
    
    # Check required figures
    print("REQUIRED FIGURES FOR PAPER")
    print("-" * 80)
    
    for figure_name, filepaths in REQUIRED_FIGURES.items():
        print(f"\n{figure_name}:")
        for filepath in filepaths:
            info = check_figure_exists(filepath)
            total_required += 1
            
            if info['exists']:
                total_found += 1
                status = "✓"
                details = f"({info['size_kb']} KB, modified: {info['modified']})"
            else:
                status = "✗"
                details = "MISSING"
                all_exist = False
            
            print(f"  {status} {info['path']:<50} {details}")
    
    # Check supplementary figures
    print("\n" + "=" * 80)
    print("SUPPLEMENTARY FIGURES (Optional)")
    print("-" * 80)
    
    supp_found = 0
    supp_total = 0
    
    for figure_name, filepaths in SUPPLEMENTARY_FIGURES.items():
        print(f"\n{figure_name}:")
        for filepath in filepaths:
            info = check_figure_exists(filepath)
            supp_total += 1
            
            if info['exists']:
                supp_found += 1
                status = "✓"
                details = f"({info['size_kb']} KB)"
            else:
                status = " "
                details = "Not available"
            
            print(f"  {status} {info['path']:<50} {details}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("-" * 80)
    print(f"Required figures: {total_found}/{total_required} found")
    print(f"Supplementary figures: {supp_found}/{supp_total} available")
    
    if all_exist:
        print("\n✅ SUCCESS: All required figures exist!")
        print("\nThe paper is ready for figure integration.")
        print("\nNEXT STEPS:")
        print("  1. Review figure quality and resolution (recommend 300+ DPI)")
        print("  2. Ensure consistent styling across all figures")
        print("  3. Add figure captions in the paper")
        print("  4. Export high-resolution versions for final submission")
        return 0
    else:
        print("\n⚠️  WARNING: Some required figures are missing!")
        print("\nTO GENERATE MISSING FIGURES:")
        print("  1. Run: python compute_lisa_all_periods.py")
        print("  2. Run: python compute_lisa_markov.py")
        print("  3. Re-run this verification script")
        return 1
    
    print()


if __name__ == "__main__":
    sys.exit(verify_figures())
