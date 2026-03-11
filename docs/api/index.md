# API Reference

The `trafficpipeline` package exposes the following modules:

| Module | Description |
|--------|-------------|
| [`config`](config.md) | City definitions, time periods, constants |
| [`utils`](utils.md) | Timestamp extraction, geometry hashing, filters |
| [`aggregate`](aggregate.md) | Raw GeoPackage → time-period aggregation |
| [`eda`](eda.md) | Data validation & exploratory analysis |
| [`geostatistics`](geostatistics.md) | Spatial statistics & hot-spot analysis |
| [`bottleneck`](bottleneck.md) | Road-capacity bottleneck analysis (OSMnx) |
| [`poi`](poi.md) | POI-congestion density analysis |
| [`synthesis`](synthesis.md) | Temporal vs spatial predictor comparison |
| [`multilevel`](multilevel.md) | Multilevel variance decomposition (mixed-effects models) |
| [`markov`](markov.md) | LISA Markov & Spatial Markov transition analysis |
| [`speed_validation`](speed_validation.md) | Speed-based validation across congestion metrics |
| [`h3_robustness`](h3_robustness.md) | H3 hexagonal aggregation for MAUP robustness |

## Importing

```python
# Import specific functions
from trafficpipeline.aggregate import aggregate_city
from trafficpipeline.config import CITIES, get_city

# Import a module
from trafficpipeline import geostatistics
geostatistics.run_analysis(base_dir=".")

# New v0.4.0 modules
from trafficpipeline.multilevel import fit_multilevel_models
from trafficpipeline.markov import compute_lisa, classic_markov, spatial_markov
from trafficpipeline.speed_validation import anova_all_metrics
from trafficpipeline.h3_robustness import h3_aggregate, resolution_sweep
```
