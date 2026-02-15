"""
Click-based CLI for the traffic-congestion-pipeline.

Entry point registered in pyproject.toml as ``traffic-pipeline``.
"""

from __future__ import annotations

from pathlib import Path

import click

from trafficpipeline import __version__


@click.group()
@click.version_option(version=__version__, prog_name="traffic-pipeline")
@click.option("--base-dir", default=".", show_default=True,
              type=click.Path(exists=True),
              help="Project root containing traffic data directories.")
@click.pass_context
def main(ctx: click.Context, base_dir: str) -> None:
    """Open-source traffic-congestion analysis pipeline."""
    ctx.ensure_object(dict)
    ctx.obj["base_dir"] = base_dir


# ── aggregate ──────────────────────────────────────────────────


@main.command()
@click.option("--city", type=click.Choice(["smg", "bdg", "jkt"]),
              help="City code (omit for all cities).")
@click.option("--column", default="JF", show_default=True,
              help="Traffic column to aggregate.")
@click.option("--verbose", is_flag=True, help="Print per-file progress.")
@click.pass_context
def aggregate(ctx: click.Context, city: str | None, column: str, verbose: bool) -> None:
    """Aggregate raw GeoPackage snapshots into time-period files."""
    from trafficpipeline.aggregate import aggregate_all, aggregate_city

    base = ctx.obj["base_dir"]
    if city:
        from trafficpipeline.config import CITIES
        info = CITIES[city]
        aggregate_city(
            city,
            traffic_column=column,
            data_dir=str(Path(base) / info["traffic_data_dir"]),
            output_dir=str(Path(base) / info["traffic_output_dir"]),
            verbose=verbose,
        )
    else:
        aggregate_all(traffic_column=column, verbose=verbose)


# ── eda ────────────────────────────────────────────────────────


@main.command()
@click.option("--output-dir", default="eda_output", show_default=True,
              help="Directory for EDA report and figures.")
@click.pass_context
def eda(ctx: click.Context, output_dir: str) -> None:
    """Run exploratory data-analysis validation."""
    from trafficpipeline.eda import main as eda_main
    eda_main()


# ── geostatistics ─────────────────────────────────────────────


@main.command()
@click.option("--figures-dir", default="figures", show_default=True)
@click.option("--output-dir", default="analysis_results", show_default=True)
@click.pass_context
def geostatistics(ctx: click.Context, figures_dir: str, output_dir: str) -> None:
    """Run spatial-statistics and hot-spot analysis."""
    from trafficpipeline.geostatistics import run_analysis
    run_analysis(
        base_dir=ctx.obj["base_dir"],
        figures_dir=figures_dir,
        output_dir=output_dir,
    )


# ── bottleneck ────────────────────────────────────────────────


@main.command()
@click.option("--figures-dir", default="figures", show_default=True)
@click.pass_context
def bottleneck(ctx: click.Context, figures_dir: str) -> None:
    """Run road-capacity bottleneck analysis."""
    from trafficpipeline.bottleneck import run_analysis
    run_analysis(base_dir=ctx.obj["base_dir"], figures_dir=figures_dir)


# ── poi ───────────────────────────────────────────────────────


@main.command()
@click.option("--figures-dir", default="figures", show_default=True)
@click.option("--output-dir", default="analysis_results", show_default=True)
@click.pass_context
def poi(ctx: click.Context, figures_dir: str, output_dir: str) -> None:
    """Run POI-congestion density analysis."""
    from trafficpipeline.poi import run_analysis
    run_analysis(
        base_dir=ctx.obj["base_dir"],
        figures_dir=figures_dir,
        output_dir=output_dir,
    )


# ── synthesis ─────────────────────────────────────────────────


@main.command()
@click.option("--figures-dir", default="figures", show_default=True)
@click.option("--output-dir", default="analysis_results", show_default=True)
@click.pass_context
def synthesis(ctx: click.Context, figures_dir: str, output_dir: str) -> None:
    """Run temporal-vs-spatial predictor comparison."""
    from trafficpipeline.synthesis import run_analysis
    run_analysis(
        base_dir=ctx.obj["base_dir"],
        figures_dir=figures_dir,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
