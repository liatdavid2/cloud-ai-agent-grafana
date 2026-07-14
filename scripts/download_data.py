#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import io
from pathlib import Path

import requests

SOURCE_URL = (
    "https://github.com/Azure/AzurePublicDataset/releases/download/dataset-v1/"
    "trace_data_vmtable_vmtable.csv.gz"
)
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
NUMERIC_INDEXES = [3, 4, 5, 6, 7, 9, 10]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream a subset of the official Microsoft Azure 2017 VM workload table."
    )
    parser.add_argument("--rows", type=int, default=10_000, help="Number of valid VM rows to keep")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--force", action="store_true", help="Replace an existing subset")
    return parser.parse_args()


def is_header(row: list[str]) -> bool:
    lowered = [value.strip().lower() for value in row]
    return lowered == COLUMNS or "vmid" in lowered


def validate_row(row: list[str]) -> list[str] | None:
    if len(row) < len(COLUMNS):
        return None
    row = row[: len(COLUMNS)]
    try:
        for index in NUMERIC_INDEXES:
            float(row[index])
    except ValueError:
        return None
    if any(not row[index].strip() for index in [0, 1, 2, 8]):
        return None
    return row


def download_subset(rows: int, output_path: Path) -> None:
    if rows <= 0:
        raise ValueError("--rows must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".part")
    written = 0
    print(f"Streaming {rows:,} valid VM rows from the official Azure trace...")

    try:
        with requests.get(SOURCE_URL, stream=True, timeout=(30, 300)) as response:
            response.raise_for_status()
            with gzip.GzipFile(fileobj=response.raw) as compressed:
                text_stream = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
                reader = csv.reader(text_stream)
                with temporary_path.open("w", encoding="utf-8", newline="") as output_file:
                    writer = csv.writer(output_file)
                    writer.writerow(COLUMNS)
                    for raw_row in reader:
                        if not raw_row or is_header(raw_row):
                            continue
                        clean_row = validate_row(raw_row)
                        if clean_row is None:
                            continue
                        writer.writerow(clean_row)
                        written += 1
                        if written >= rows:
                            break
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    if written < rows:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(f"Only {written:,} valid rows were available; expected {rows:,}")

    temporary_path.replace(output_path)
    print(f"Saved {written:,} real Azure VM rows to {output_path}")


def main() -> None:
    args = parse_args()
    output_path = args.output_dir / f"azure_vm_usage_{args.rows}.csv"
    if output_path.exists() and not args.force:
        print(f"Dataset already exists; skipping download: {output_path}")
        return
    download_subset(args.rows, output_path)


if __name__ == "__main__":
    main()
