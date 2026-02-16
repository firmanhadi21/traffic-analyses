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


# ── collect ────────────────────────────────────────────────────


@main.command()
@click.option("--city", multiple=True,
              type=click.Choice(["smg", "bdg", "jkt"]),
              help="City codes to collect (omit for all cities).")
@click.option("--api-key", envvar="HERE_API_KEY", required=True,
              help="HERE API key (default: $HERE_API_KEY).")
@click.option("--interval", default=900, show_default=True, type=int,
              help="Seconds between collection cycles (0 = once).")
@click.option("--once", is_flag=True,
              help="Collect once and exit.")
@click.option("--output-dir", default=None,
              help="Override base output directory.")
@click.pass_context
def collect(ctx: click.Context, city: tuple[str, ...], api_key: str,
            interval: int, once: bool, output_dir: str | None) -> None:
    """Collect traffic flow data from the HERE Traffic API v7."""
    import logging
    import time

    from trafficpipeline.collector import collect_all as _collect_all

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-8s  %(message)s")

    city_codes = list(city) if city else None
    run_once = once or interval == 0

    cycle = 0
    while True:
        cycle += 1
        click.echo(f"── Cycle {cycle} ──")
        t0 = time.time()
        paths = _collect_all(
            api_key=api_key,
            city_codes=city_codes,
            output_base=output_dir,
        )
        for p in paths:
            click.echo(f"  ✓ {p}")
        click.echo(f"Cycle {cycle}: {len(paths)} files in {time.time()-t0:.1f}s")

        if run_once:
            break
        time.sleep(max(0, interval - (time.time() - t0)))


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
