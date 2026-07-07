"""Positive-control analysis: free-flow speed as a spatial predictor of current speed.

Thin wrapper around :mod:`trafficpipeline.positive_control` so the analysis can
be run from the repository root without installing the package:

    python positive_control_analysis.py

Equivalent to ``traffic-pipeline positive-control``. See the package module for
the methodology description. Outputs analysis_results/positive_control_r2.csv.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from trafficpipeline.positive_control import run_analysis

if __name__ == "__main__":
    run_analysis(base_dir=Path(__file__).parent,
                 output_dir=Path(__file__).parent / "analysis_results")
