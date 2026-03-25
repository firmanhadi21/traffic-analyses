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
# traffic-pipeline, version 0.4.2

traffic-pipeline --help
```

## Requirements

- **Python ≥ 3.9**
- Core dependencies are installed automatically: GeoPandas, OSMnx, NetworkX,
  SciPy, Matplotlib, Seaborn, Click, and others.

### Data Collection (Optional)

Data collection is now fully Python-based using the `traffic-pipeline collect`
command. You'll need a traffic API key from one of the supported providers
(HERE, TomTom, or Google). Pre-aggregated data is available on
[Zenodo](https://doi.org/10.5281/zenodo.19211072) if you want to skip collection.
