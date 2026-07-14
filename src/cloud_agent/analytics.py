from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def short_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _vm_records(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["vm_id"] = work["vmid"].map(short_id)
    work["deployment_id"] = work["deploymentid"].map(short_id)
    return work


def dataset_summary(frame: pd.DataFrame) -> dict:
    return {
        "rows": int(len(frame)),
        "unique_vms": int(frame["vmid"].nunique()),
        "subscriptions": int(frame["subscriptionid"].nunique()),
        "deployments": int(frame["deploymentid"].nunique()),
        "avg_cpu": round(float(frame["avgcpu"].mean()), 3),
        "avg_p95_cpu": round(float(frame["p95maxcpu"].mean()), 3),
        "avg_cores": round(float(frame["vmcorecount"].mean()), 3),
        "avg_memory_gb": round(float(frame["vmmemory"].mean()), 3),
        "total_core_hours": round(float(frame["core_hours"].sum()), 3),
        "median_lifetime_hours": round(float(frame["lifetime_hours"].median()), 3),
    }


def high_cpu_vms(frame: pd.DataFrame, threshold: float = 80, limit: int = 20) -> list[dict]:
    work = _vm_records(frame)
    selected = work[work["avgcpu"] >= threshold].sort_values(
        ["avgcpu", "p95maxcpu", "maxcpu"], ascending=False
    )
    columns = [
        "vm_id", "deployment_id", "vmcategory", "avgcpu", "p95maxcpu", "maxcpu",
        "vmcorecount", "vmmemory", "lifetime_hours",
    ]
    return selected.head(limit)[columns].round(3).to_dict(orient="records")


def underutilized_vms(
    frame: pd.DataFrame,
    threshold: float = 10,
    min_lifetime_hours: float = 24,
    limit: int = 20,
) -> list[dict]:
    work = _vm_records(frame)
    selected = work[
        (work["avgcpu"] <= threshold)
        & (work["p95maxcpu"] <= max(threshold * 2, threshold + 5))
        & (work["lifetime_hours"] >= min_lifetime_hours)
    ].sort_values(["core_hours", "avgcpu"], ascending=[False, True])
    columns = [
        "vm_id", "deployment_id", "vmcategory", "avgcpu", "p95maxcpu",
        "vmcorecount", "vmmemory", "lifetime_hours", "core_hours",
    ]
    return selected.head(limit)[columns].round(3).to_dict(orient="records")


def rightsizing_candidates(
    frame: pd.DataFrame,
    max_avg_cpu: float = 20,
    max_p95_cpu: float = 40,
    min_cores: int = 2,
    limit: int = 20,
) -> list[dict]:
    work = _vm_records(frame)
    selected = work[
        (work["avgcpu"] <= max_avg_cpu)
        & (work["p95maxcpu"] <= max_p95_cpu)
        & (work["vmcorecount"] >= min_cores)
    ].copy()
    selected["recommended_cores"] = np.maximum(1, np.ceil(selected["vmcorecount"] / 2)).astype(int)
    selected["potential_core_reduction"] = selected["vmcorecount"] - selected["recommended_cores"]
    selected = selected.sort_values(["potential_core_reduction", "core_hours"], ascending=False)
    columns = [
        "vm_id", "deployment_id", "vmcategory", "avgcpu", "p95maxcpu",
        "vmcorecount", "recommended_cores", "potential_core_reduction",
        "vmmemory", "lifetime_hours",
    ]
    return selected.head(limit)[columns].round(3).to_dict(orient="records")


def cpu_anomalies(frame: pd.DataFrame, z_threshold: float = 3.0, limit: int = 20) -> list[dict]:
    values = frame["avgcpu"].astype(float)
    std = float(values.std(ddof=0))
    if std == 0 or np.isnan(std):
        return []
    work = _vm_records(frame)
    work["z_score"] = (work["avgcpu"] - float(values.mean())) / std
    work = work[work["z_score"].abs() >= z_threshold].copy()
    work["abs_z"] = work["z_score"].abs()
    work = work.sort_values("abs_z", ascending=False)
    columns = [
        "vm_id", "deployment_id", "vmcategory", "avgcpu", "p95maxcpu",
        "maxcpu", "vmcorecount", "vmmemory", "z_score",
    ]
    return work.head(limit)[columns].round(3).to_dict(orient="records")


def category_summary(frame: pd.DataFrame) -> list[dict]:
    grouped = (
        frame.groupby("vmcategory", as_index=False)
        .agg(
            vms=("vmid", "size"),
            avg_cpu=("avgcpu", "mean"),
            avg_p95_cpu=("p95maxcpu", "mean"),
            avg_cores=("vmcorecount", "mean"),
            avg_memory_gb=("vmmemory", "mean"),
            total_core_hours=("core_hours", "sum"),
        )
        .sort_values("total_core_hours", ascending=False)
    )
    return grouped.round(3).to_dict(orient="records")


def deployment_summary(frame: pd.DataFrame, limit: int = 20) -> list[dict]:
    grouped = (
        frame.groupby("deploymentid", as_index=False)
        .agg(
            vm_count=("vmid", "size"),
            avg_cpu=("avgcpu", "mean"),
            peak_cpu=("maxcpu", "max"),
            total_cores=("vmcorecount", "sum"),
            total_memory_gb=("vmmemory", "sum"),
            total_core_hours=("core_hours", "sum"),
        )
        .sort_values("total_core_hours", ascending=False)
        .head(limit)
    )
    grouped["deployment_id"] = grouped["deploymentid"].map(short_id)
    return grouped.drop(columns=["deploymentid"]).round(3).to_dict(orient="records")


def kpis(frame: pd.DataFrame) -> dict:
    return {
        "vms": int(len(frame)),
        "high_cpu_vms": int((frame["avgcpu"] >= 80).sum()),
        "underutilized_vms": int(
            ((frame["avgcpu"] <= 10) & (frame["p95maxcpu"] <= 20) & (frame["lifetime_hours"] >= 24)).sum()
        ),
        "rightsizing_candidates": int(
            ((frame["avgcpu"] <= 20) & (frame["p95maxcpu"] <= 40) & (frame["vmcorecount"] >= 2)).sum()
        ),
    }
