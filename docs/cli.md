# CLI Reference

The `traffic-pipeline` command provides sub-commands for each stage of the
analysis pipeline.

## Global options

```
traffic-pipeline [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--base-dir PATH` | Project root directory (default: current directory) |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

---

## `collect`

Collect traffic data from **any city worldwide** using HERE, TomTom, or Google APIs.

```bash
traffic-pipeline collect [OPTIONS]
```

### Collection Modes

The `collect` command supports three modes:

1. **Custom bounding box** - Specify exact coordinates
2. **City name geocoding** - Auto-lookup city boundaries via OpenStreetMap
3. **Preconfigured cities** - Use built-in Indonesian cities (backward compatible)

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--bbox` | TEXT | - | Bounding box: `WEST,SOUTH,EAST,NORTH` |
| `--city-name` | TEXT | - | City name to geocode (repeatable) |
| `--city` | CHOICE | *(all)* | Preconfigured city code (`smg`, `bdg`, `jkt`) |
| `--provider` | CHOICE | `here` | Provider (`here`, `tomtom`, `google`) |
| `--api-key` | TEXT | *(required)* | Traffic API key |
| `--output-dir` | TEXT | *(auto)* | Output directory |
| `--interval` | INT | `900` | Collection interval in seconds |
| `--once` | FLAG | - | Collect once and exit |

### Examples

**Collect from any city using bounding box:**

```bash
# London, UK
traffic-pipeline collect --bbox -0.5,51.3,0.3,51.7 --output-dir london_data --once

# New York City, USA
traffic-pipeline collect --bbox -74.05,40.63,-73.75,40.85 --output-dir nyc_data --once
```

**Collect using city name (auto-geocoded):**

```bash
# Single city
traffic-pipeline collect --city-name "Paris, France" --once

# Multiple cities
traffic-pipeline collect --city-name "Paris" --city-name "London" --interval 900
```

> **Note:** City name geocoding uses OpenStreetMap Nominatim. Be specific with country names to avoid ambiguity (e.g., "Paris, France" not just "Paris").

**Preconfigured cities (backward compatible):**

```bash
# Single city
traffic-pipeline collect --city smg --once

# Multiple cities
traffic-pipeline collect --city smg --city bdg --interval 900

# All configured cities
traffic-pipeline collect --once
```

### Supported Providers

| Provider | API | Status |
|----------|-----|--------|
| `here` | HERE Traffic Flow v7 | ✅ Tested |
| `tomtom` | TomTom Flow Segment Data v4 | ⚠️ Not tested with live API |
| `google` | Google Routes API v2 | ⚠️ Experimental |

---

## `aggregate`

Aggregate raw GeoPackage snapshots into time-period files.

```bash
traffic-pipeline aggregate [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--city` | TEXT | *(all cities)* | City code (`smg`, `bdg`, `jkt`) |
| `--column` | TEXT | `jam_factor` | Traffic column to aggregate |
| `--verbose / --no-verbose` | FLAG | `--verbose` | Print progress |

---

## `eda`

Run exploratory data-analysis validation.

```bash
traffic-pipeline eda [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output-dir` | PATH | `eda_output` | Directory for EDA reports |

---

## `geostatistics`

Run spatial statistics and hot-spot analysis.

```bash
traffic-pipeline geostatistics [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |

---

## `bottleneck`

Run road-capacity bottleneck analysis (requires OSMnx network download).

```bash
traffic-pipeline bottleneck [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |

---

## `poi`

Run POI-congestion density analysis.

```bash
traffic-pipeline poi [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |

---

## `synthesis`

Run temporal vs spatial predictor comparison.

```bash
traffic-pipeline synthesis [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |

---

## `multilevel`

Run multilevel variance decomposition using mixed-effects models.
Fits null → temporal → full models on absolute speed (km/h) to partition
within-segment (temporal) and between-segment (spatial) variance.

```bash
traffic-pipeline multilevel [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |

### Outputs

- `multilevel_results.csv` — ICC, temporal R², spatial ΔR² per city
- `multilevel_variance_decomposition.png` — grouped bar chart

!!! note "Dependency"
    Requires `statsmodels` (included in core dependencies since v0.4.0).

---

## `markov`

Run LISA Markov and Spatial Markov transition analysis. Computes LISA
categories per segment per time period, then fits classic and spatial
Markov models to quantify hotspot persistence and spatial contagion.

```bash
traffic-pipeline markov [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |

### Outputs

- `markov_analysis_results.csv` — persistence probabilities, contagion test results
- `markov/<city>_transition_matrix.png` — heatmap per city
- `markov/persistence_comparison.png` — cross-city comparison
- `markov/spatial_contagion_test.png` — chi-squared results

!!! note "Dependency"
    Requires PySAL extras: `pip install traffic-congestion-pipeline[pysal]`

---

## `speed-validation`

Run speed-based validation across multiple congestion metrics (jam factor,
current speed, speed reduction, free-flow speed). Confirms that temporal
dominance is not an artifact of jam factor normalization.

```bash
traffic-pipeline speed-validation [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |

### Outputs

- `speed_validation_anova.csv` — η² per city × metric
- `centrality_by_metric.csv` — centrality R² per metric type
- `speed_validation_eta_squared.png` — grouped bar chart
- `centrality_r2_by_metric.png` — centrality correlation comparison

---

## `h3-robustness`

Run H3 hexagonal aggregation at multiple spatial resolutions to test whether
null spatial autocorrelation results persist at neighbourhood scales
(MAUP robustness check).

```bash
traffic-pipeline h3-robustness [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--figures-dir` | PATH | `figures` | Directory for output figures |
| `--output-dir` | PATH | `analysis_results` | Directory for CSV results |
| `--period` | TEXT | `evening_peak` | Time period to analyze |

### Outputs

- `h3_robustness_results.csv` — Moran's I at each resolution per city
- `h3_resolution_sweep.png` — line plot of Moran's I and p-values across scales
- `h3_map_<city>_res8.png` — choropleth per city at resolution 8

!!! note "Dependency"
    Requires H3 extras: `pip install traffic-congestion-pipeline[h3]`
