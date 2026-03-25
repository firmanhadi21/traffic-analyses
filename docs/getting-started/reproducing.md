# Reproducing the Analysis

Follow these steps to reproduce all results from the archived dataset.

## 1. Clone & install

```bash
git clone https://github.com/firmanhadi21/traffic-analyses.git
cd traffic-analyses

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[all]"
```

## 2. Download data from Zenodo

Download the dataset from
[doi:10.5281/zenodo.19211072](https://doi.org/10.5281/zenodo.19211072) and
unzip.  Place the three `traffic_*_output/` directories in the repository root:

```
traffic-analyses/
├── traffic_smg_output/   ← from Zenodo
├── traffic_bdg_output/   ← from Zenodo
└── traffic_jkt_output/   ← from Zenodo
```

## 3. Verify

```bash
traffic-pipeline --version
pytest tests/ -v              # requires pip install -e ".[dev]"
```

## 4. Run the pipeline

```bash
traffic-pipeline geostatistics    # Spatial statistics & hot-spot maps
traffic-pipeline bottleneck       # Road-capacity bottleneck analysis
traffic-pipeline poi              # POI-congestion density analysis
traffic-pipeline synthesis        # Temporal vs spatial comparison
traffic-pipeline multilevel       # Multilevel variance decomposition
traffic-pipeline markov           # LISA Markov transition analysis
traffic-pipeline speed-validation # Speed-based metric validation
traffic-pipeline h3-robustness    # H3 hexagonal MAUP robustness
```

Results are written to `figures/` (PNG) and `analysis_results/` (CSV).

## Expected runtime

| Stage | Approximate time |
|-------|-----------------|
| `geostatistics` | 2–5 minutes |
| `bottleneck` | 10–30 minutes (downloads OSMnx networks) |
| `poi` | 5–15 minutes (downloads POI data) |
| `synthesis` | < 1 minute |
| `multilevel` | 2–10 minutes |
| `markov` | 5–15 minutes (LISA permutations) |
| `speed-validation` | 1–3 minutes |
| `h3-robustness` | 2–5 minutes |
