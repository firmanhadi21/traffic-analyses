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

Use the Python-based collector with your traffic API key:

```bash
# Collect once for the new city
export TRAFFIC_API_KEY=your_key_here
traffic-pipeline collect --city sby --provider here --api-key $TRAFFIC_API_KEY --once
```

For continuous collection, you can use the built-in daemon mode:

```bash
# Run as daemon (every 15 minutes)
traffic-pipeline collect --city sby --provider here --api-key $TRAFFIC_API_KEY --interval 900
```

Or set up cron for scheduled collection:

```bash
# Every 15 minutes
*/15 * * * * /path/to/.venv/bin/traffic-pipeline collect --city sby --provider here --api-key YOUR_KEY --once >> /path/to/logs/cron.log 2>&1
```

Or use macOS launchd (see `com.trafficpipeline.collector.plist` for reference).

## 3. Run the pipeline

```bash
traffic-pipeline aggregate --city sby
traffic-pipeline geostatistics
traffic-pipeline bottleneck
traffic-pipeline poi
traffic-pipeline synthesis
```

All downstream stages automatically pick up the new city from the config.
