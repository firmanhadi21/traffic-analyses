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
              help="Preconfigured city codes (backward compatible).")
@click.option("--city-name", multiple=True,
              help="City name to geocode (e.g., 'Paris, France').")
@click.option("--bbox",
              help="Bounding box: WEST,SOUTH,EAST,NORTH (e.g., '-74.05,40.63,-73.75,40.85').")
@click.option("--provider", type=click.Choice(["here", "tomtom", "google", "mapbox"]),
              default="here", show_default=True,
              help="Traffic data provider.")
@click.option("--api-key", envvar="TRAFFIC_API_KEY", required=True,
              help="API key (default: $TRAFFIC_API_KEY env var).")
@click.option("--interval", default=900, show_default=True, type=int,
              help="Seconds between collection cycles (0 = once).")
@click.option("--once", is_flag=True,
              help="Collect once and exit.")
@click.option("--output-dir", default=None,
              help="Output directory for collected data.")
@click.pass_context
def collect(ctx: click.Context, city: tuple[str, ...], city_name: tuple[str, ...],
            bbox: str | None, provider: str, api_key: str, interval: int,
            once: bool, output_dir: str | None) -> None:
    """Collect traffic data from any city worldwide.
    
    Three collection modes:
    
    \b
    1. Preconfigured cities: --city smg --city bdg
    2. Custom bounding box: --bbox -74.05,40.63,-73.75,40.85 --output-dir nyc_data
    3. Geocoded city: --city-name "Paris, France" --city-name "London, UK"
    
    Examples:
    
    \b
    # Collect from New York using bounding box
    traffic-pipeline collect --bbox -74.05,40.63,-73.75,40.85 --output-dir nyc --once
    
    \b
    # Collect from Paris using city name
    traffic-pipeline collect --city-name "Paris, France" --once
    
    \b
    # Backward compatible: Indonesian cities
    traffic-pipeline collect --city smg --city bdg --once
    """
    import logging
    import time
    from datetime import datetime
    from pathlib import Path

    import pytz

    from trafficpipeline.collector import collect_all as _collect_all_legacy
    from trafficpipeline.collector import get_provider
    from trafficpipeline.config import TIMEZONE

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s"
    )
    logger = logging.getLogger(__name__)

    run_once = once or interval == 0
    
    # Parse collection targets (priority: bbox > city-name > city > all)
    targets = []
    
    if bbox:
        # Direct bbox
        from trafficpipeline.geocoding import parse_bbox_string
        parsed = parse_bbox_string(bbox)
        if not parsed:
            click.echo(f"Error: Invalid bbox: {bbox}", err=True)
            raise click.Abort()
        targets.append({
            "name": "custom",
            "bbox": parsed,
            "output_dir": output_dir or "traffic_data_custom",
        })
    
    elif city_name:
        # Geocode city names
        from trafficpipeline.geocoding import geocode_city
        for name in city_name:
            result = geocode_city(name)
            if not result:
                click.echo(f"Error: Could not geocode '{name}'", err=True)
                raise click.Abort()
            
            safe_name = result['name'].lower().replace(' ', '_').replace(',', '')
            targets.append({
                "name": result['name'],
                "bbox": result['bbox'],
                "output_dir": output_dir or f"traffic_data_{safe_name}",
            })
            click.echo(f"✓ Geocoded: {result['display_name']}")
    
    elif city:
        # Legacy: use configured cities
        cycle = 0
        while True:
            cycle += 1
            click.echo(f"── Cycle {cycle} ({provider}) ──")
            t0 = time.time()
            paths = _collect_all_legacy(
                api_key=api_key,
                city_codes=list(city),
                output_base=output_dir,
                provider_name=provider,
            )
            for p in paths:
                click.echo(f"  ✓ {p}")
            click.echo(f"Cycle {cycle}: {len(paths)} files in {time.time()-t0:.1f}s")
            if run_once:
                break
            time.sleep(max(0, interval - (time.time() - t0)))
        return
    
    else:
        # Default: all configured cities
        cycle = 0
        while True:
            cycle += 1
            click.echo(f"── Cycle {cycle} ({provider}) ──")
            t0 = time.time()
            paths = _collect_all_legacy(
                api_key=api_key,
                city_codes=None,
                output_base=output_dir,
                provider_name=provider,
            )
            for p in paths:
                click.echo(f"  ✓ {p}")
            click.echo(f"Cycle {cycle}: {len(paths)} files in {time.time()-t0:.1f}s")
            if run_once:
                break
            time.sleep(max(0, interval - (time.time() - t0)))
        return
    
    # Dynamic collection loop (bbox / city-name)
    provider_obj = get_provider(provider, api_key)
    cycle = 0
    
    while True:
        cycle += 1
        click.echo(f"── Cycle {cycle} ({provider}) ──")
        t0 = time.time()
        paths = []
        
        for target in targets:
            try:
                gdf = provider_obj.fetch_flow(target["bbox"])
                
                if len(gdf) == 0:
                    logger.warning("No data for %s", target["name"])
                    continue
                
                # Save GeoPackage
                out_dir = Path(target["output_dir"])
                out_dir.mkdir(parents=True, exist_ok=True)
                
                tz = pytz.timezone(TIMEZONE)
                now = datetime.now(tz)
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                
                filename = f"{target['name']}_traffic_{timestamp}.gpkg"
                outpath = out_dir / filename
                
                gdf.to_file(outpath, driver="GPKG")
                logger.info("Saved %d segments → %s", len(gdf), outpath)
                paths.append(outpath)
                click.echo(f"  ✓ {outpath}")
                
            except Exception:
                logger.exception("Failed to collect %s", target["name"])
        
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
