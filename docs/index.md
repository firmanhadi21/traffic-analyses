# Traffic Congestion Pipeline

[![PyPI](https://img.shields.io/pypi/v/traffic-congestion-pipeline.svg)](https://pypi.org/project/traffic-congestion-pipeline/)
[![CI](https://github.com/firmanhadi21/traffic-analyses/actions/workflows/test.yml/badge.svg)](https://github.com/firmanhadi21/traffic-analyses/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/firmanhadi21/traffic-analyses/blob/main/LICENSE)

An **open-source, installable Python pipeline** for spatiotemporal traffic
congestion analysis, integrating the HERE Traffic API, OSMnx, and PySAL.

Designed for reproducible urban analytics across Indonesian metropolitan
cities: **Semarang**, **Bandung**, and **Jakarta**.

## Features

- **Six-stage analysis pipeline**: aggregate → EDA → geostatistics → bottleneck → POI → synthesis
- **CLI and Python API**: Use `traffic-pipeline` from the terminal or import modules directly
- **264 million observations** across 18,694 road segments over 11 months
- **Reproducible**: Zenodo-archived dataset + installable package + CI

## Quick Start

```bash
pip install traffic-congestion-pipeline
traffic-pipeline --help
```

See the [Installation](getting-started/installation.md) and
[Quick Start](getting-started/quickstart.md) guides for details.

## Cities Covered

| City | Segments | Coverage |
|------|----------|----------|
| Semarang | 1,076 | Urban core |
| Bandung | 3,069 | Metropolitan area |
| Jakarta | 14,549 | Greater Jakarta |

## Data Availability

The aggregated dataset (24 GeoPackages — 8 time periods × 3 cities) is
archived on Zenodo:

> **Hadi, F., Wahyuddin, Y., Sabri, L. M., & Indrajit, A.** (2026).
> Traffic Congestion Dataset: Semarang, Bandung, Jakarta (2025–2026).
> *Zenodo*. [doi:10.5281/zenodo.18650759](https://doi.org/10.5281/zenodo.18650759)

## License

MIT — see [LICENSE](https://github.com/firmanhadi21/traffic-analyses/blob/main/LICENSE).
