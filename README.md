# Project Aftershock: Automated Seismic Data Pipeline & Claims Triage

An end-to-end automated data engineering pipeline designed to ingest, validate, clean, and enrich real-time seismic event data from the USGS API alongside regional ground-motion sensor logs. The pipeline automates high-priority risk flagging to dramatically reduce manual insurance adjuster review overhead.

---

## 🏗️ Architecture & Pipeline Flow

1. **Extraction (`USGS GeoJSON API`):** Fetches real-time seismic events and extracts unique identifiers to `data/raw/extracted_ids.txt`.
2. **Sensor Log Synthesis (`generate_aftershock_log.py`):** Generates synthetic ground telemetry (`data/raw/regional_sensor_log.csv`) with simulated network dropouts and ghost IDs to stress-test data integrity pipelines.
3. **ETL & Data Cleaning (`src/pipeline.py`):**
   - Resolves outer joins and filters unverified ghost IDs.
   - Cleans anomalous readings, handles missing values, and normalizes timestamps.
   - Computes derived feature `significant` (flagging events with `magnitude >= 5.0`).
   - Exports high-integrity dataset to `data/processed/clean_data.csv`.
4. **Exploratory Data Analysis (`notebooks/exploration.ipynb`):** Validates missingness rates, distribution statistics, and data quality metrics.

---

## 📊 Business ROI & Metric Analysis

### 1. Workload Reduction (ROI Metric)
* **Total Processed Events:** `884`
* **Significant Flagged Events (Mag >= 5.0):** `54`
* **Workload Reduction:** **`93.89%`**

> **Business Impact:** By automatically triaging incoming seismic events and only escalating events with `magnitude >= 5.0` for detailed manual claims review, the operations team achieves a **93.89% reduction** in manual workload (reducing ticket volume from 884 to just 54 high-priority cases).

### 2. Validation Check (Significance Score Comparison)
* **Average Significance Score (`significant = 1`):** **`480.48`**
* **Average Significance Score (`significant = 0`):** **`248.33`**

> **Validation Insight:** The average USGS significance score for flagged critical events (`480.48`) is substantially higher than routine events (`248.33`), confirming that the triage heuristic successfully isolates high-severity seismic activity without letting false negatives slip through.

---

## 📁 Repository Structure

```text
project_aftershock/
│
├── data/
│   ├── raw/
│   │   ├── extracted_ids.txt            # Extracted USGS event IDs
│   │   └── regional_sensor_log.csv      # Raw ground-sensor logs
│   └── processed/
│       └── clean_data.csv               # Cleaned, merged, and enriched dataset
│
├── notebooks/
│   └── exploration.ipynb                # Data exploration and quality verification
│
├── src/
│   └── pipeline.py                      # Core automated ETL pipeline script
│
├── generate_aftershock_log.py           # Mock sensor log generator
└── README.md                            # Project documentation and performance metrics