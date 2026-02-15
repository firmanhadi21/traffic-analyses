# Adding a New City

The pipeline is designed to be extensible.  Adding a new city requires three
steps.

## 1. Register the city in config

Add an entry to the `CITIES` dictionary in
[`src/trafficpipeline/config.py`](https://github.com/firmanhadi21/traffic-analyses/blob/main/src/trafficpipeline/config.py):

```python
CITIES["sby"] = {
    "name": "Surabaya",
    "bbox": (112.60, -7.40, 112.85, -7.20),
    "bbox_dict": {
        "west": 112.60,
        "south": -7.40,
        "east": 112.85,
        "north": -7.20,
    },
    "traffic_data_dir": "traffic_data_sby",
    "traffic_output_dir": "traffic_sby_output",
    "filename_pattern": "surabaya_traffic_*.gpkg",
    "expected_segments": 5000,
    "color": "#9b59b6",
}
```

### Key fields

| Field | Description |
|-------|-------------|
| `bbox` | `(west, south, east, north)` bounding box in WGS 84 |
| `bbox_dict` | Same bbox as a dict (used by some OSMnx calls) |
| `traffic_data_dir` | Directory for raw GeoPackage snapshots |
| `traffic_output_dir` | Directory for aggregated output |
| `filename_pattern` | Glob pattern for raw files |
| `expected_segments` | Approximate segment count (for progress bars) |
| `color` | Hex colour used in multi-city plots |

## 2. Collect data

Update the bounding-box coordinates in `traffic_collector.R` and run the
R-based collector (requires a HERE API key):

```bash
Rscript traffic_collector.R
```

Or set up cron for continuous collection:

```bash
# Every 15 minutes
*/15 * * * * /path/to/traffic_collector.sh >> output.log 2>> error.log
```

## 3. Run the pipeline

```bash
traffic-pipeline aggregate --city sby
traffic-pipeline geostatistics
traffic-pipeline bottleneck
traffic-pipeline poi
traffic-pipeline synthesis
```

All downstream stages automatically pick up the new city from the config.
