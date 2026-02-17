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

Collect traffic data from supported providers (HERE, TomTom, Google).

```bash
traffic-pipeline collect [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--provider` | TEXT | `here` | Provider (`here`, `tomtom`, `google`) |
| `--api-key` | TEXT | *(required)* | Traffic API key for the selected provider |
| `--city` | TEXT | *(all cities)* | City code (`smg`, `bdg`, `jkt`) |
| `--once` | FLAG | *(disabled)* | Collect once and exit (default: continuous) |
| `--interval` | INT | `900` | Collection interval in seconds (15 min default) |

### Examples

```bash
# Collect once for all cities using HERE
traffic-pipeline collect --provider here --api-key $YOUR_KEY --once

# Collect for a specific city
traffic-pipeline collect --city smg --provider here --api-key $KEY --once

# Run as daemon (every 15 minutes)
traffic-pipeline collect --provider here --api-key $KEY --interval 900

# Use TomTom provider
traffic-pipeline collect --provider tomtom --api-key $TOMTOM_KEY --once
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
