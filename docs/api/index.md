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

## Importing

```python
# Import specific functions
from trafficpipeline.aggregate import aggregate_city
from trafficpipeline.config import CITIES, get_city

# Import a module
from trafficpipeline import geostatistics
geostatistics.run_analysis(base_dir=".")
```
