# Quick Start

After [installing](installation.md) the package, you can use either the CLI
or the Python API.

## CLI

```bash
# Run geostatistical analysis (requires data in traffic_*_output/ dirs)
traffic-pipeline geostatistics

# Run bottleneck analysis (downloads OSMnx road network)
traffic-pipeline bottleneck

# Point at a custom data directory
traffic-pipeline --base-dir /path/to/data geostatistics
```

All commands:

| Command | Description |
|---------|-------------|
| `aggregate` | Aggregate raw GeoPackage snapshots into time-period files |
| `eda` | Exploratory data analysis and validation |
| `geostatistics` | Spatial statistics and hot-spot maps |
| `bottleneck` | Road-capacity bottleneck analysis (OSMnx) |
| `poi` | POI-congestion density analysis |
| `synthesis` | Temporal vs spatial predictor comparison |

See the full [CLI Reference](../cli.md) for all options.

## Python API

```python
from trafficpipeline.aggregate import aggregate_city
from trafficpipeline.geostatistics import run_analysis
from trafficpipeline.config import CITIES

# Aggregate a single city
aggregate_city("jkt", traffic_column="JF", verbose=True)

# Run geostatistical analysis
run_analysis(base_dir=".", figures_dir="figures")

# List available cities
print(list(CITIES.keys()))  # ['smg', 'bdg', 'jkt']
```

## Output

Results are written to:

- `figures/` — PNG visualisations
- `analysis_results/` — CSV statistical summaries
- `eda_output/` — EDA validation reports
