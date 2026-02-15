#!/usr/bin/env python3
"""
Update Manuscript with Analysis Results

This script reads all analysis results from CSV files and updates
the manuscript tables and removes TODO comments.

Run after HPC analysis is complete.
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime

MANUSCRIPT_PATH = Path("paper/manuscript.md")
RESULTS_DIR = Path("analysis_results")


def load_results():
    """Load all analysis results from CSV files"""
    results = {}

    # Moran's I
    morans_path = RESULTS_DIR / "morans_i_results.csv"
    if morans_path.exists():
        results['morans'] = pd.read_csv(morans_path)
        print(f"✓ Loaded Moran's I results")

    # LISA
    lisa_path = RESULTS_DIR / "lisa_results.csv"
    if lisa_path.exists():
        results['lisa'] = pd.read_csv(lisa_path)
        print(f"✓ Loaded LISA results")

    # ANOVA
    anova_path = RESULTS_DIR / "anova_results.csv"
    if anova_path.exists():
        results['anova'] = pd.read_csv(anova_path)
        print(f"✓ Loaded ANOVA results")

    # Centrality correlations
    corr_path = RESULTS_DIR / "centrality_correlations.csv"
    if corr_path.exists():
        results['centrality'] = pd.read_csv(corr_path)
        print(f"✓ Loaded centrality correlation results")
    else:
        print(f"⚠ Centrality correlations not found - run HPC analysis first")

    return results


def format_p_value(p):
    """Format p-value for display"""
    if pd.isna(p):
        return "—"
    if p < 0.001:
        return "< 0.001"
    elif p < 0.01:
        return f"{p:.3f}"
    else:
        return f"{p:.3f}"


def format_correlation(r):
    """Format correlation coefficient"""
    if pd.isna(r):
        return "—"
    return f"{r:.3f}"


def generate_morans_table(df):
    """Generate Moran's I table in markdown format"""
    lines = [
        "| City | Moran's I | Z-score | p-value | Interpretation |",
        "|------|-----------|---------|---------|----------------|"
    ]

    for _, row in df.iterrows():
        city = row['City']
        I = row['Moran_I']
        z = row['Z_score']
        p = row['p_value']

        if pd.isna(I):
            interp = "—"
        elif p < 0.05:
            interp = "Clustered" if I > 0 else "Dispersed"
        else:
            interp = "Random"

        I_str = f"{I:.4f}" if not pd.isna(I) else "—"
        z_str = f"{z:.2f}" if not pd.isna(z) else "—"
        p_str = format_p_value(p)

        lines.append(f"| {city} | {I_str} | {z_str} | {p_str} | {interp} |")

    return "\n".join(lines)


def generate_lisa_table(df):
    """Generate LISA cluster table in markdown format"""
    lines = [
        "| City | HH (Hotspot) | LL (Coldspot) | HL (Outlier) | LH (Outlier) | Not Significant |",
        "|------|--------------|---------------|--------------|--------------|-----------------|"
    ]

    for _, row in df.iterrows():
        city = row['City']
        hh = int(row['HH_Hotspots']) if not pd.isna(row['HH_Hotspots']) else 0
        ll = int(row['LL_Coldspots']) if not pd.isna(row['LL_Coldspots']) else 0
        hl = int(row['HL_Outliers']) if not pd.isna(row['HL_Outliers']) else 0
        lh = int(row['LH_Outliers']) if not pd.isna(row['LH_Outliers']) else 0
        ns = int(row['Not_Significant']) if not pd.isna(row['Not_Significant']) else 0

        lines.append(f"| {city} | {hh} | {ll} | {hl} | {lh} | {ns} |")

    return "\n".join(lines)


def generate_anova_table(df):
    """Generate ANOVA results table in markdown format"""
    lines = [
        "| City | F-statistic | p-value | Significant Period Pairs |",
        "|------|-------------|---------|--------------------------|"
    ]

    for _, row in df.iterrows():
        city = row['City']
        f_stat = row['F_statistic']
        p = row['p_value']
        sig_pairs = row['Significant_pairs']

        f_str = f"{f_stat:,.2f}"
        p_str = format_p_value(p)
        pairs_str = f"{int(sig_pairs)}/28" if not pd.isna(sig_pairs) else "—"

        lines.append(f"| {city} | {f_str} | {p_str} | {pairs_str} |")

    return "\n".join(lines)


def generate_centrality_table(df):
    """Generate centrality-congestion correlation table in markdown format"""
    lines = [
        "| City | n | Pearson r | p-value | Spearman ρ | p-value |",
        "|------|---|-----------|---------|------------|---------|"
    ]

    for _, row in df.iterrows():
        city = row['city']
        n = int(row['n_matched'])
        pr = format_correlation(row['pearson_r'])
        pp = format_p_value(row['pearson_p'])
        sr = format_correlation(row['spearman_r'])
        sp = format_p_value(row['spearman_p'])

        lines.append(f"| {city} | {n:,} | {pr} | {pp} | {sr} | {sp} |")

    return "\n".join(lines)


def remove_todo_comments(content):
    """Remove all TODO comments from manuscript"""
    # Pattern to match TODO blocks (multi-line)
    # Matches lines starting with TODO and subsequent indented lines
    patterns = [
        r'\n*<!-- TODO:.*?-->\n*',  # HTML-style TODO comments
        r'\n*TODO:.*?(?=\n[A-Z#|]|\n\n|\Z)',  # TODO: blocks
        r'\n*\*TODO:.*?\*\n*',  # *TODO:* style
    ]

    for pattern in patterns:
        content = re.sub(pattern, '\n', content, flags=re.DOTALL | re.MULTILINE)

    # Remove lines that are just "TODO" or start with "TODO"
    lines = content.split('\n')
    filtered_lines = []
    skip_until_blank = False

    for line in lines:
        stripped = line.strip()

        # Skip TODO lines and their continuation
        if stripped.startswith('TODO'):
            skip_until_blank = True
            continue

        # Reset skip flag on blank line or new section
        if skip_until_blank:
            if stripped == '' or stripped.startswith('#') or stripped.startswith('|'):
                skip_until_blank = False
            else:
                continue

        filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def update_manuscript(results):
    """Update manuscript with new results"""
    print(f"\nReading manuscript from {MANUSCRIPT_PATH}...")

    with open(MANUSCRIPT_PATH, 'r') as f:
        content = f.read()

    original_content = content

    # Update Table 7: Moran's I (find and replace)
    if 'morans' in results:
        print("Updating Table 7 (Moran's I)...")
        new_table = generate_morans_table(results['morans'])

        # Find the Moran's I table section and update it
        # Look for pattern: Table 7 header followed by table
        pattern = r'(\*\*Table 7[^*]*\*\*[^\n]*\n\n)(\|[^\n]*\n\|[-|]+\n(?:\|[^\n]*\n)+)'

        if re.search(pattern, content):
            content = re.sub(pattern, r'\1' + new_table + '\n', content)
            print("  ✓ Table 7 updated")
        else:
            print("  ⚠ Could not find Table 7 pattern")

    # Update Table 8: LISA clusters
    if 'lisa' in results:
        print("Updating Table 8 (LISA clusters)...")
        new_table = generate_lisa_table(results['lisa'])

        pattern = r'(\*\*Table 8[^*]*\*\*[^\n]*\n\n)(\|[^\n]*\n\|[-|]+\n(?:\|[^\n]*\n)+)'

        if re.search(pattern, content):
            content = re.sub(pattern, r'\1' + new_table + '\n', content)
            print("  ✓ Table 8 updated")
        else:
            print("  ⚠ Could not find Table 8 pattern")

    # Update Table 9: ANOVA
    if 'anova' in results:
        print("Updating Table 9 (ANOVA)...")
        new_table = generate_anova_table(results['anova'])

        # ANOVA might be in a different table number, search flexibly
        pattern = r'(\*\*Table \d+[^*]*ANOVA[^*]*\*\*[^\n]*\n\n)(\|[^\n]*\n\|[-|]+\n(?:\|[^\n]*\n)+)'

        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, r'\1' + new_table + '\n', content, flags=re.IGNORECASE)
            print("  ✓ ANOVA table updated")
        else:
            print("  ⚠ Could not find ANOVA table pattern")

    # Update Table 10: Centrality correlations
    if 'centrality' in results:
        print("Updating Table 10 (Centrality correlations)...")
        new_table = generate_centrality_table(results['centrality'])

        pattern = r'(\*\*Table 10[^*]*\*\*[^\n]*\n\n)(\|[^\n]*\n\|[-|]+\n(?:\|[^\n]*\n)+)'

        if re.search(pattern, content):
            content = re.sub(pattern, r'\1' + new_table + '\n', content)
            print("  ✓ Table 10 updated")
        else:
            print("  ⚠ Could not find Table 10 pattern")

    # Remove TODO comments
    print("\nRemoving TODO comments...")
    todo_count = len(re.findall(r'TODO', content, re.IGNORECASE))
    content = remove_todo_comments(content)
    new_todo_count = len(re.findall(r'TODO', content, re.IGNORECASE))
    print(f"  Removed {todo_count - new_todo_count} TODO references")

    # Check if content changed
    if content != original_content:
        # Backup original
        backup_path = MANUSCRIPT_PATH.with_suffix('.md.backup')
        with open(backup_path, 'w') as f:
            f.write(original_content)
        print(f"\n✓ Backup saved to {backup_path}")

        # Write updated manuscript
        with open(MANUSCRIPT_PATH, 'w') as f:
            f.write(content)
        print(f"✓ Manuscript updated: {MANUSCRIPT_PATH}")
    else:
        print("\nNo changes made to manuscript")

    return content


def generate_results_summary(results):
    """Generate a summary of all results for quick reference"""
    summary = []
    summary.append("=" * 70)
    summary.append("ANALYSIS RESULTS SUMMARY")
    summary.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary.append("=" * 70)

    if 'morans' in results:
        summary.append("\n## Global Moran's I")
        summary.append("-" * 40)
        for _, row in results['morans'].iterrows():
            p = row['p_value']
            sig = "significant" if p < 0.05 else "not significant"
            summary.append(f"{row['City']}: I = {row['Moran_I']:.4f} ({sig}, p = {p:.4f})")

    if 'lisa' in results:
        summary.append("\n## LISA Clusters")
        summary.append("-" * 40)
        for _, row in results['lisa'].iterrows():
            total = row['HH_Hotspots'] + row['LL_Coldspots'] + row['HL_Outliers'] + row['LH_Outliers']
            summary.append(f"{row['City']}: {int(total)} significant clusters "
                          f"(HH={int(row['HH_Hotspots'])}, LL={int(row['LL_Coldspots'])})")

    if 'anova' in results:
        summary.append("\n## ANOVA Results")
        summary.append("-" * 40)
        for _, row in results['anova'].iterrows():
            summary.append(f"{row['City']}: F = {row['F_statistic']:,.2f}, p < 0.001 "
                          f"({int(row['Significant_pairs'])}/28 pairs significant)")

    if 'centrality' in results:
        summary.append("\n## Centrality-Congestion Correlations")
        summary.append("-" * 40)
        for _, row in results['centrality'].iterrows():
            r = row['pearson_r']
            p = row['pearson_p']
            sig = "*" if p < 0.05 else ""
            strength = "weak" if abs(r) < 0.3 else "moderate" if abs(r) < 0.5 else "strong"
            direction = "positive" if r > 0 else "negative"
            summary.append(f"{row['city']}: r = {r:.3f}{sig} ({strength} {direction})")

    summary.append("\n" + "=" * 70)

    return "\n".join(summary)


def main():
    print("=" * 70)
    print("MANUSCRIPT UPDATE TOOL")
    print("=" * 70)

    # Load results
    print("\nLoading analysis results...")
    results = load_results()

    if not results:
        print("\n⚠ No results found. Run analyses first.")
        return

    # Generate summary
    summary = generate_results_summary(results)
    print(summary)

    # Save summary
    summary_path = RESULTS_DIR / "results_summary.txt"
    with open(summary_path, 'w') as f:
        f.write(summary)
    print(f"\n✓ Summary saved to {summary_path}")

    # Update manuscript
    update_manuscript(results)

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Review updated manuscript: paper/manuscript.md")
    print("2. Check backup if needed: paper/manuscript.md.backup")
    print("3. Verify tables are correctly formatted")
    print("4. Update Discussion section with interpretations")
    print("5. Commit changes to git")


if __name__ == "__main__":
    main()
