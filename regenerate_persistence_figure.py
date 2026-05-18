#!/usr/bin/env python3
"""Regenerate figures/markov/persistence_analysis.png using the FIXED
strict-alignment LISA Markov pipeline (src/trafficpipeline/markov.py).

The previous figure was produced by the legacy compute_lisa_markov.py
script against combined_lisa.gpkg (segments not measured in some periods
were implicitly classified NS, inflating "ever in category" counts).
The new figure is computed on segments aligned across all 8 periods.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from trafficpipeline import markov
from trafficpipeline.config import CITIES

BASE = Path(__file__).resolve().parent
OUT  = BASE / "figures" / "markov" / "persistence_analysis.png"

print("Computing LISA panels under strict alignment for all three cities...")

results: dict = {}
for code, info in CITIES.items():
    print(f"  {info['name']}...")
    y, _ = markov.build_lisa_matrix(code, base_dir=str(BASE))
    results[code] = {
        "n_aligned": y.shape[0],
        "persistence": markov.persistence_statistics(y),
    }
    print(f"    aligned n = {y.shape[0]}")

print("Rendering persistence figure...")

fig, axes = plt.subplots(1, 3, figsize=(14, 5))
CATEGORIES = ["HH", "LL", "HL", "LH"]

for ax, (code, info) in zip(axes, CITIES.items()):
    if code not in results:
        continue
    m = results[code]["persistence"]
    ever_pcts   = [m[c]["ever_pct"] for c in CATEGORIES]
    always_pcts = [m[c]["always_pct"] for c in CATEGORIES]

    x = np.arange(len(CATEGORIES))
    w = 0.35
    bars_e = ax.bar(x - w/2, ever_pcts, w, label="Ever in category",
                    color="steelblue", alpha=0.75)
    bars_a = ax.bar(x + w/2, always_pcts, w, label="Always in category",
                    color="darkred", alpha=0.75)

    ax.set_xlabel("LISA Category", fontsize=11)
    ax.set_ylabel("% of Segments", fontsize=11)
    n_aligned = results[code]["n_aligned"]
    ax.set_title(f"{info['name']} (n={n_aligned:,})", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(CATEGORIES, fontsize=10)
    ax.legend(fontsize=9, loc="upper right")
    ax.set_ylim(0, max(ever_pcts) * 1.3 if max(ever_pcts) else 1)
    ax.grid(axis="y", alpha=0.3)

    for bar in bars_e:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8)
    for bar in bars_a:
        if bar.get_height() > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8)

fig.suptitle(
    "Temporal Persistence of LISA Clusters under Strict Across-Period Alignment\n"
    "(Segments measured in all 8 daily periods)",
    fontsize=13, fontweight="bold", y=1.02,
)
plt.tight_layout()
plt.savefig(OUT, dpi=150, bbox_inches="tight")
plt.close()
print(f"Saved: {OUT}")
