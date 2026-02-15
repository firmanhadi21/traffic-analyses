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
