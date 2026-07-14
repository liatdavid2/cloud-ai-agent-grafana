from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = [
    "vmid",
    "subscriptionid",
    "deploymentid",
    "vmcreated",
    "vmdeleted",
    "maxcpu",
    "avgcpu",
    "p95maxcpu",
    "vmcategory",
    "vmcorecount",
    "vmmemory",
]
NUMERIC_COLUMNS = [
    "vmcreated",
    "vmdeleted",
    "maxcpu",
    "avgcpu",
    "p95maxcpu",
    "vmcorecount",
    "vmmemory",
]


def load_dataset(path: str | Path) -> pd.DataFrame:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {dataset_path}. Run scripts/download_data.py first."
        )

    frame = pd.read_csv(dataset_path)
    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    frame = frame[COLUMNS].copy()
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["vmid", "subscriptionid", "deploymentid", "vmcategory"]:
        frame[column] = frame[column].astype(str)

    frame = frame.dropna(subset=COLUMNS).copy()
    frame["lifetime_hours"] = ((frame["vmdeleted"] - frame["vmcreated"]) / 3600).clip(lower=0)
    frame["core_hours"] = frame["lifetime_hours"] * frame["vmcorecount"]
    return frame.sort_values(["vmcreated", "vmid"]).reset_index(drop=True)
