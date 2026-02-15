# Installation

## From PyPI

```bash
pip install traffic-congestion-pipeline
```

### Optional extras

```bash
# With PySAL spatial econometrics (libpysal, esda, spreg)
pip install "traffic-congestion-pipeline[pysal]"

# Full install (PySAL + Folium + Contextily)
pip install "traffic-congestion-pipeline[all]"

# Developer install (adds pytest, pytest-cov)
pip install "traffic-congestion-pipeline[dev]"
```

## From Source

```bash
git clone https://github.com/firmanhadi21/traffic-analyses.git
cd traffic-analyses
pip install -e ".[dev]"
```

## Verify

```bash
traffic-pipeline --version
# traffic-pipeline, version 0.1.0

traffic-pipeline --help
```

## Requirements

- **Python ≥ 3.9**
- Core dependencies are installed automatically: GeoPandas, OSMnx, NetworkX,
  SciPy, Matplotlib, Seaborn, Click, and others.

### R (data collection only)

The data-collection step uses the [hereR](https://github.com/munterfinger/hereR)
R package.  This is **not required** for analysis — pre-aggregated data is
available on [Zenodo](https://doi.org/10.5281/zenodo.18650759).

```r
install.packages(c("hereR", "sf", "lubridate"))
```
