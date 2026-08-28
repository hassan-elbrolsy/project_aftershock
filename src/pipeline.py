"""
src/pipeline.py — Regional Seismic Risk Triage End-to-End Pipeline.
Adheres strictly to standard library Python (no pandas, numpy, or bs4).
"""

import csv
import json
import sys
from pathlib import Path
import requests

# Allow importing from root directory
sys.path.append(str(Path(__file__).resolve().parent.parent))
from generate_aftershock_log import generate_aftershock_log


def scrape_great_earthquake_threshold() -> float:
    """Scrapes the magnitude floor for 'great' earthquakes from Alaska Earthquake Center."""
    url = "https://earthquake.alaska.edu/earthquake-magnitude-classes"
    fallback_threshold = 8.0
    anchor = "magnitudes greater than"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        html_text = response.text

        if anchor in html_text:
            start_idx = html_text.find(anchor) + len(anchor)
            window = html_text[start_idx : start_idx + 25].strip()
            token = window.split()[0].rstrip(".,;:<>/\"'")
            return float(token)
        return fallback_threshold
    except requests.exceptions.RequestException:
        return fallback_threshold


def fetch_usgs_earthquakes(starttime: str = "2024-01-01", 
                           endtime: str = "2024-01-15", 
                           minmagnitude: float = 2.5) -> list[dict]:
    """Queries the USGS FDSN Event API for seismic events."""
    endpoint = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "starttime": starttime,
        "endtime": endtime,
        "minmagnitude": minmagnitude,
    }

    try:
        response = requests.get(endpoint, params=params, timeout=15)
        response.raise_for_status()
        return response.json().get("features", [])
    except requests.exceptions.RequestException as err:
        print(f"[Error] Failed to fetch USGS data: {err}")
        return []


def calculate_median(values: list[float]) -> float:
    """Computes median using pure Python sorting."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return float(sorted_vals[mid])
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def calculate_mean(values: list[float]) -> float:
    """Computes mean using running accumulator."""
    if not values:
        return 0.0
    running_sum = 0.0
    count = 0
    for v in values:
        running_sum += v
        count += 1
    return running_sum / count if count > 0 else 0.0


def parse_place_field(place_str: str | None) -> tuple[str, str]:
    """Splits place string into distance/direction prefix and region."""
    if not place_str:
        return "Unknown Distance", "Unknown Region"
    if " of " in place_str:
        parts = place_str.split(" of ", 1)
        return parts[0].strip(), parts[1].strip()
    return "Direct Location", place_str.strip()


def run_pipeline():
    """Runs data extraction, cleaning, imputation, scaling, and CSV packaging."""
    root_dir = Path(__file__).resolve().parent.parent
    raw_dir = root_dir / "data" / "raw"
    proc_dir = root_dir / "data" / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)

    # 1. Scrape Anchor
    great_thresh = scrape_great_earthquake_threshold()

    # 2. Ingest API Records
    records = fetch_usgs_earthquakes()
    if not records:
        print("[Pipeline Aborted] No records fetched.")
        return

    # 3. Extract IDs and Generate Sensor Log
    event_ids = [f["id"] for f in records if "id" in f]
    ids_file = raw_dir / "extracted_ids.txt"
    ids_file.write_text("\n".join(event_ids), encoding="utf-8")

    sensor_log_path = raw_dir / "regional_sensor_log.csv"
    generate_aftershock_log(event_ids, output_path=sensor_log_path, seed=42)

    # 4. Cohort Filtering
    earthquake_cohort = [
        r for r in records if r.get("properties", {}).get("type") == "earthquake"
    ]

    # 5. Imputation medians
    gaps = [r["properties"]["gap"] for r in earthquake_cohort if r.get("properties", {}).get("gap") is not None]
    dmins = [r["properties"]["dmin"] for r in earthquake_cohort if r.get("properties", {}).get("dmin") is not None]
    nsts = [r["properties"]["nst"] for r in earthquake_cohort if r.get("properties", {}).get("nst") is not None]

    median_gap = calculate_median([float(x) for x in gaps])
    median_dmin = calculate_median([float(x) for x in dmins])
    median_nst = calculate_median([float(x) for x in nsts])

    # 6. Transform & Feature Engineering
    cleaned_rows = []
    for rec in earthquake_cohort:
        props = rec.get("properties", {})
        coords = rec.get("geometry", {}).get("coordinates", [None, None, None])

        depth_km = coords[2] if len(coords) > 2 and coords[2] is not None else 0.0
        mag = float(props.get("mag")) if props.get("mag") is not None else 0.0

        # Semantic Imputation
        felt = int(props["felt"]) if props.get("felt") is not None else 0
        cdi = float(props["cdi"]) if props.get("cdi") is not None else 0.0

        # Statistical Imputation
        gap = float(props["gap"]) if props.get("gap") is not None else median_gap
        dmin = float(props["dmin"]) if props.get("dmin") is not None else median_dmin
        nst = int(props["nst"]) if props.get("nst") is not None else int(median_nst)

        sig = int(props.get("sig", 0)) if props.get("sig") is not None else 0
        tsunami = int(props.get("tsunami", 0)) if props.get("tsunami") is not None else 0

        dist_prefix, region = parse_place_field(props.get("place"))

        # Depth Categorization
        if depth_km < 70.0:
            depth_cat = "shallow"
        elif 70.0 <= depth_km <= 300.0:
            depth_cat = "intermediate"
        else:
            depth_cat = "deep"

        pct_great = (mag / great_thresh) * 100.0
        significant = 1 if mag >= 5.0 else 0

        cleaned_rows.append({
            "event_id": rec.get("id"),
            "mag": mag,
            "depth_km": depth_km,
            "longitude": coords[0],
            "latitude": coords[1],
            "felt": felt,
            "cdi": cdi,
            "mmi": float(props["mmi"]) if props.get("mmi") is not None else 0.0,
            "alert": str(props.get("alert") or "none"),
            "gap": gap,
            "dmin": dmin,
            "nst": nst,
            "sig": sig,
            "tsunami": tsunami,
            "distance_prefix": dist_prefix,
            "region": region,
            "depth_category": depth_cat,
            "pct_of_great_threshold": round(pct_great, 2),
            "significant": significant,
        })

    # 7. Defensive Join with regional_sensor_log.csv
    sensor_lookup = {}
    if sensor_log_path.exists():
        with sensor_log_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sensor_lookup[row["event_id"].strip()] = {
                    "station_network": row.get("station_network", "").strip(),
                    "local_claims_filed": row.get("local_claims_filed", "").strip(),
                }

    for row in cleaned_rows:
        log_match = sensor_lookup.get(row["event_id"], {})
        row["station_network"] = log_match.get("station_network", "UNLINKED")
        raw_claims = log_match.get("local_claims_filed", "")
        if raw_claims in ("", "N/A", "null"):
            row["local_claims_filed"] = 0
        else:
            try:
                row["local_claims_filed"] = int(raw_claims)
            except ValueError:
                row["local_claims_filed"] = 0

    # 8. Min-Max Scaling on mag
    all_mags = [r["mag"] for r in cleaned_rows]
    min_mag = min(all_mags) if all_mags else 0.0
    max_mag = max(all_mags) if all_mags else 1.0
    mag_range = (max_mag - min_mag) if (max_mag - min_mag) != 0 else 1.0

    for row in cleaned_rows:
        row["scaled_mag"] = round((row["mag"] - min_mag) / mag_range, 4)

    # 9. Validation Check & ROI Calculation
    sig_1 = [r["sig"] for r in cleaned_rows if r["significant"] == 1]
    sig_0 = [r["sig"] for r in cleaned_rows if r["significant"] == 0]

    n_total = len(cleaned_rows)
    n_flagged = len(sig_1)
    reduction = (1.0 - (n_flagged / n_total)) * 100.0 if n_total > 0 else 0.0

    print("\n--- Pipeline Execution Summary ---")
    print(f"Processed Events: {n_total}")
    print(f"Significant Flagged Events: {n_flagged}")
    print(f"Workload Reduction (ROI): {reduction:.2f}%")
    print(f"Avg Sig (significant=1): {calculate_mean(sig_1):.2f}")
    print(f"Avg Sig (significant=0): {calculate_mean(sig_0):.2f}\n")

    # 10. Write Clean CSV Output
    output_csv = proc_dir / "clean_data.csv"
    if cleaned_rows:
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(cleaned_rows[0].keys()))
            writer.writeheader()
            writer.writerows(cleaned_rows)
        print(f"[Success] Clean data written to: {output_csv}")


if __name__ == "__main__":
    run_pipeline()