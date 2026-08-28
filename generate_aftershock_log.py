#!/usr/bin/env python3
"""
generate_aftershock_log.py — Project Aftershock synthetic log generator.
"""

import argparse
import csv
import random
from pathlib import Path

DEFAULT_OUTPUT = Path("data/raw/regional_sensor_log.csv")
FIELDNAMES = ["event_id", "station_network", "local_claims_filed"]

STATION_NETWORKS = ["PNSN-07", "CEA-12", "USGS-WEST", "SCEDC-01", " PNSN-07\t"]

DROP_RATE = 0.10
GHOST_RATE = 0.10
DIRTY_RATE = 0.15

FALLBACK_IDS = [
    "uw714067081", "us7000py0f", "uw62242312", "ak0257jjjpjt", "uw62216847",
    "uw62197602", "uw62064837", "uw61976681", "ak024k7m66d", "uw61960946",
]


def _dirty_claims_filed():
    clean_val = random.randint(0, 15)
    if random.random() < DIRTY_RATE:
        return random.choice(["", "N/A", "null", "0", f" {clean_val} "])
    return str(clean_val)


def _fabricate_ghost_id(used_ids):
    prefixes = ["uw", "us", "ak", "nn", "ci", "nc"]
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    while True:
        prefix = random.choice(prefixes)
        suffix = "".join(random.choice(alphabet) for _ in range(random.choice([8, 9, 10])))
        candidate = f"{prefix}{suffix}"
        if candidate not in used_ids:
            return candidate


def generate_aftershock_log(id_list, output_path=None, seed=None):
    if seed is not None:
        random.seed(seed)

    output_path = Path(output_path) if output_path else DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ids = [str(i).strip() for i in id_list if str(i).strip()]

    n_drop = round(len(ids) * DROP_RATE)
    dropped = set(random.sample(ids, n_drop)) if n_drop else set()
    surviving_ids = [i for i in ids if i not in dropped]

    n_ghost = round(len(ids) * GHOST_RATE)
    used_ids = set(ids)
    ghost_ids = []
    for _ in range(n_ghost):
        ghost = _fabricate_ghost_id(used_ids)
        used_ids.add(ghost)
        ghost_ids.append(ghost)

    all_ids = surviving_ids + ghost_ids
    random.shuffle(all_ids)

    rows = [
        {
            "event_id": event_id,
            "station_network": random.choice(STATION_NETWORKS),
            "local_claims_filed": _dirty_claims_filed(),
        }
        for event_id in all_ids
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"[generate_aftershock_log] {len(ids)} input ids -> {len(rows)} log rows "
        f"({len(dropped)} dropped, {len(ghost_ids)} ghost ids injected) -> {output_path}"
    )
    return output_path


def _load_ids_from_file(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Could not find {p}.")
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _cli():
    parser = argparse.ArgumentParser(description="Generate synthetic sensor log.")
    parser.add_argument("--input-ids", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.input_ids:
        ids = _load_ids_from_file(args.input_ids)
    else:
        ids = FALLBACK_IDS

    generate_aftershock_log(ids, output_path=args.output, seed=args.seed)


if __name__ == "__main__":
    _cli()