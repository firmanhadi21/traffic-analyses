# Legacy Collection System (DEPRECATED)

> [!WARNING]
> **This document describes the legacy R-based data collection system.**
>
> The traffic collection pipeline has been migrated to **pure Python** as of February 2026.
> This file and the associated R scripts (`traffic_collector.R`, `traffic_collector.sh`) are
> preserved for historical reference only.

## Current System

The traffic pipeline is now **fully Python-based** with multi-provider support:

- **Collection**: Use `traffic-pipeline collect` command
- **Providers**: HERE, TomTom, Google (provider-agnostic architecture)
- **Scheduling**: Built-in daemon mode, cron, or macOS launchd
- **Documentation**: See [Installation](docs/getting-started/installation.md) and [CLI Reference](docs/cli.md)

### Quick Migration

If you were using the R scripts:

```bash
# Old (R-based)
Rscript traffic_collector.R

# New (Python-based)
traffic-pipeline collect --provider here --api-key $YOUR_KEY --once
```

For continuous collection:

```bash
# Built-in daemon (replaces cron)
traffic-pipeline collect --provider here --api-key $YOUR_KEY --interval 900
```

## Historical Documentation

The original system collected traffic data for Indonesian cities using the `hereR` R package wrapper around the HERE Traffic API. While functional, it had limitations:

- Single provider (HERE only)
- Required R environment and dependencies
- Separate cron/shell scripting for scheduling
- Less flexible for extension

The new Python system addresses these limitations while maintaining backward compatibility with the GeoPackage data format.

## Aggregation Pipeline

As of March 2026, the aggregation pipeline uses **OSM-based segment matching** (`osm_composite_id`) instead of the legacy FID-based approach. The primary key in all aggregated GeoPackages is `osm_composite_id`, which is a composite identifier derived from the OSM reference network. See `run_osm_aggregation.py` and `src/trafficpipeline/aggregate.py` for implementation.

---

**For current usage, see the main [README.md](README.md) and [docs/](docs/).**
