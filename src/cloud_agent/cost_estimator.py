from __future__ import annotations

import os
from typing import Any

import pandas as pd


DEFAULT_PRICE_PER_CORE_HOUR = float(
    os.getenv(
        "PRICE_PER_CORE_HOUR",
        "0.045",
    )
)

DEFAULT_PRICE_PER_GB_HOUR = float(
    os.getenv(
        "PRICE_PER_GB_HOUR",
        "0.006",
    )
)

DEFAULT_MONTHLY_HOURS = float(
    os.getenv(
        "MONTHLY_HOURS",
        "730",
    )
)


COLUMN_ALIASES: dict[str, list[str]] = {
    "vm_id": [
        "vm_id",
        "vmid",
        "vm_identifier",
        "vm_hash",
    ],
    "deployment_id": [
        "deployment_id",
        "deploymentid",
        "deployment",
        "deployment_hash",
    ],
    "avg_cpu": [
        "avg_cpu",
        "avgcpu",
        "mean_cpu",
        "average_cpu",
        "cpu_average",
    ],
    "p95_cpu": [
        "p95_cpu",
        "p95maxcpu",
        "p95_max_cpu",
        "cpu_p95",
        "max_cpu_p95",
    ],
    "cores": [
        "cores",
        "vmcorecount",
        "core_count",
        "allocated_cores",
        "cpu_cores",
    ],
    "memory_gb": [
        "memory_gb",
        "vmmemory",
        "memory",
        "allocated_memory_gb",
        "memory_size_gb",
    ],
    "lifetime_hours": [
        "lifetime_hours",
        "lifetime",
        "duration_hours",
        "vm_lifetime_hours",
    ],
    "core_hours": [
        "core_hours",
        "total_core_hours",
        "allocated_core_hours",
    ],
    "category": [
        "category",
        "vm_category",
        "vmcategory",
        "workload_category",
    ],
}


def _find_column(
    frame: pd.DataFrame,
    logical_name: str,
    required: bool = True,
) -> str | None:
    aliases = COLUMN_ALIASES[logical_name]

    normalized_columns = {
        str(column).lower(): str(column)
        for column in frame.columns
    }

    for alias in aliases:
        if alias.lower() in normalized_columns:
            return normalized_columns[alias.lower()]

    if required:
        raise ValueError(
            f"Could not find a column for '{logical_name}'. "
            f"Expected one of: {aliases}. "
            f"Available columns: {list(frame.columns)}"
        )

    return None


def _safe_numeric(
    series: pd.Series,
    default: float = 0.0,
) -> pd.Series:
    return (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        .fillna(default)
        .astype(float)
    )


def _prepare_cost_frame(
    frame: pd.DataFrame,
    price_per_core_hour: float,
    price_per_gb_hour: float,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    result = frame.copy()

    cores_col = _find_column(
        result,
        "cores",
    )

    memory_col = _find_column(
        result,
        "memory_gb",
        required=False,
    )

    lifetime_col = _find_column(
        result,
        "lifetime_hours",
    )

    core_hours_col = _find_column(
        result,
        "core_hours",
        required=False,
    )

    cores = _safe_numeric(
        result[cores_col]
    )

    lifetime_hours = _safe_numeric(
        result[lifetime_col]
    ).clip(lower=0)

    if core_hours_col:
        core_hours = _safe_numeric(
            result[core_hours_col]
        ).clip(lower=0)
    else:
        core_hours = cores * lifetime_hours

    if memory_col:
        memory_gb = _safe_numeric(
            result[memory_col]
        ).clip(lower=0)
    else:
        memory_gb = pd.Series(
            0.0,
            index=result.index,
        )

    memory_gb_hours = (
        memory_gb
        * lifetime_hours
    )

    compute_cost = (
        core_hours
        * price_per_core_hour
    )

    memory_cost = (
        memory_gb_hours
        * price_per_gb_hour
    )

    result["_estimated_core_hours"] = core_hours
    result["_estimated_memory_gb_hours"] = memory_gb_hours
    result["_estimated_compute_cost"] = compute_cost
    result["_estimated_memory_cost"] = memory_cost
    result["_estimated_total_cost"] = (
        compute_cost
        + memory_cost
    )

    return result


def estimate_vm_costs(
    frame: pd.DataFrame,
    limit: int = 20,
    price_per_core_hour: float = DEFAULT_PRICE_PER_CORE_HOUR,
    price_per_gb_hour: float = DEFAULT_PRICE_PER_GB_HOUR,
) -> list[dict[str, Any]]:
    """
    Estimate historical infrastructure cost for each VM.

    The estimate uses:
    core-hours × price per core-hour
    +
    memory GB-hours × price per GB-hour

    These are model-based estimates and not actual Azure invoices.
    """

    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero"
        )

    result = _prepare_cost_frame(
        frame=frame,
        price_per_core_hour=price_per_core_hour,
        price_per_gb_hour=price_per_gb_hour,
    )

    if result.empty:
        return []

    vm_id_col = _find_column(
        result,
        "vm_id",
        required=False,
    )

    avg_cpu_col = _find_column(
        result,
        "avg_cpu",
        required=False,
    )

    cores_col = _find_column(
        result,
        "cores",
    )

    memory_col = _find_column(
        result,
        "memory_gb",
        required=False,
    )

    lifetime_col = _find_column(
        result,
        "lifetime_hours",
    )

    result = result.sort_values(
        "_estimated_total_cost",
        ascending=False,
    ).head(limit)

    rows: list[dict[str, Any]] = []

    for index, row in result.iterrows():
        rows.append(
            {
                "vm_id": (
                    str(row[vm_id_col])
                    if vm_id_col
                    else str(index)
                ),
                "avg_cpu": round(
                    float(row[avg_cpu_col]),
                    2,
                )
                if avg_cpu_col
                else None,
                "cores": round(
                    float(row[cores_col]),
                    2,
                ),
                "memory_gb": round(
                    float(row[memory_col]),
                    2,
                )
                if memory_col
                else None,
                "lifetime_hours": round(
                    float(row[lifetime_col]),
                    2,
                ),
                "estimated_core_hours": round(
                    float(
                        row[
                            "_estimated_core_hours"
                        ]
                    ),
                    2,
                ),
                "estimated_compute_cost_usd": round(
                    float(
                        row[
                            "_estimated_compute_cost"
                        ]
                    ),
                    2,
                ),
                "estimated_memory_cost_usd": round(
                    float(
                        row[
                            "_estimated_memory_cost"
                        ]
                    ),
                    2,
                ),
                "estimated_total_cost_usd": round(
                    float(
                        row[
                            "_estimated_total_cost"
                        ]
                    ),
                    2,
                ),
            }
        )

    return rows


def estimate_deployment_costs(
    frame: pd.DataFrame,
    limit: int = 20,
    price_per_core_hour: float = DEFAULT_PRICE_PER_CORE_HOUR,
    price_per_gb_hour: float = DEFAULT_PRICE_PER_GB_HOUR,
) -> list[dict[str, Any]]:
    """
    Estimate cost grouped by deployment.
    """

    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero"
        )

    result = _prepare_cost_frame(
        frame=frame,
        price_per_core_hour=price_per_core_hour,
        price_per_gb_hour=price_per_gb_hour,
    )

    if result.empty:
        return []

    deployment_col = _find_column(
        result,
        "deployment_id",
    )

    vm_id_col = _find_column(
        result,
        "vm_id",
        required=False,
    )

    avg_cpu_col = _find_column(
        result,
        "avg_cpu",
        required=False,
    )

    aggregations: dict[str, Any] = {
        "_estimated_core_hours": "sum",
        "_estimated_memory_gb_hours": "sum",
        "_estimated_compute_cost": "sum",
        "_estimated_memory_cost": "sum",
        "_estimated_total_cost": "sum",
    }

    if avg_cpu_col:
        aggregations[avg_cpu_col] = "mean"

    if vm_id_col:
        aggregations[vm_id_col] = pd.Series.nunique

    grouped = (
        result.groupby(
            deployment_col,
            dropna=False,
        )
        .agg(aggregations)
        .reset_index()
    )

    grouped = grouped.sort_values(
        "_estimated_total_cost",
        ascending=False,
    ).head(limit)

    rows: list[dict[str, Any]] = []

    for _, row in grouped.iterrows():
        item: dict[str, Any] = {
            "deployment_id": str(
                row[deployment_col]
            ),
            "estimated_core_hours": round(
                float(
                    row[
                        "_estimated_core_hours"
                    ]
                ),
                2,
            ),
            "estimated_compute_cost_usd": round(
                float(
                    row[
                        "_estimated_compute_cost"
                    ]
                ),
                2,
            ),
            "estimated_memory_cost_usd": round(
                float(
                    row[
                        "_estimated_memory_cost"
                    ]
                ),
                2,
            ),
            "estimated_total_cost_usd": round(
                float(
                    row[
                        "_estimated_total_cost"
                    ]
                ),
                2,
            ),
        }

        if avg_cpu_col:
            item["avg_cpu"] = round(
                float(row[avg_cpu_col]),
                2,
            )

        if vm_id_col:
            item["vm_count"] = int(
                row[vm_id_col]
            )

        rows.append(item)

    return rows


def estimate_monthly_cost(
    frame: pd.DataFrame,
    price_per_core_hour: float = DEFAULT_PRICE_PER_CORE_HOUR,
    price_per_gb_hour: float = DEFAULT_PRICE_PER_GB_HOUR,
    monthly_hours: float = DEFAULT_MONTHLY_HOURS,
) -> dict[str, Any]:
    """
    Estimate normalized monthly cost based on current allocations.

    This is different from historical trace cost. It assumes the
    observed VM allocations remain active for `monthly_hours`.
    """

    if frame.empty:
        return {
            "vm_count": 0,
            "estimated_monthly_cost_usd": 0.0,
            "estimated_monthly_compute_cost_usd": 0.0,
            "estimated_monthly_memory_cost_usd": 0.0,
        }

    cores_col = _find_column(
        frame,
        "cores",
    )

    memory_col = _find_column(
        frame,
        "memory_gb",
        required=False,
    )

    vm_id_col = _find_column(
        frame,
        "vm_id",
        required=False,
    )

    cores = _safe_numeric(
        frame[cores_col]
    ).clip(lower=0)

    if memory_col:
        memory_gb = _safe_numeric(
            frame[memory_col]
        ).clip(lower=0)
    else:
        memory_gb = pd.Series(
            0.0,
            index=frame.index,
        )

    compute_cost = (
        cores.sum()
        * monthly_hours
        * price_per_core_hour
    )

    memory_cost = (
        memory_gb.sum()
        * monthly_hours
        * price_per_gb_hour
    )

    vm_count = (
        int(frame[vm_id_col].nunique())
        if vm_id_col
        else int(len(frame))
    )

    return {
        "vm_count": vm_count,
        "monthly_hours": monthly_hours,
        "price_per_core_hour_usd": (
            price_per_core_hour
        ),
        "price_per_gb_hour_usd": (
            price_per_gb_hour
        ),
        "estimated_monthly_compute_cost_usd": round(
            compute_cost,
            2,
        ),
        "estimated_monthly_memory_cost_usd": round(
            memory_cost,
            2,
        ),
        "estimated_monthly_cost_usd": round(
            compute_cost + memory_cost,
            2,
        ),
        "estimation_note": (
            "Model-based estimate using configurable "
            "core-hour and memory GB-hour prices. "
            "This is not an Azure invoice."
        ),
    }


def find_expensive_underutilized_vms(
    frame: pd.DataFrame,
    max_avg_cpu: float = 10,
    max_p95_cpu: float = 20,
    min_lifetime_hours: float = 24,
    limit: int = 20,
    price_per_core_hour: float = DEFAULT_PRICE_PER_CORE_HOUR,
    price_per_gb_hour: float = DEFAULT_PRICE_PER_GB_HOUR,
) -> list[dict[str, Any]]:
    """
    Find VMs with low utilization and high estimated cost.
    """

    result = _prepare_cost_frame(
        frame=frame,
        price_per_core_hour=price_per_core_hour,
        price_per_gb_hour=price_per_gb_hour,
    )

    if result.empty:
        return []

    avg_cpu_col = _find_column(
        result,
        "avg_cpu",
    )

    p95_cpu_col = _find_column(
        result,
        "p95_cpu",
        required=False,
    )

    lifetime_col = _find_column(
        result,
        "lifetime_hours",
    )

    cores_col = _find_column(
        result,
        "cores",
    )

    vm_id_col = _find_column(
        result,
        "vm_id",
        required=False,
    )

    avg_cpu = _safe_numeric(
        result[avg_cpu_col]
    )

    lifetime = _safe_numeric(
        result[lifetime_col]
    )

    mask = (
        (avg_cpu <= max_avg_cpu)
        & (lifetime >= min_lifetime_hours)
    )

    if p95_cpu_col:
        p95_cpu = _safe_numeric(
            result[p95_cpu_col]
        )

        mask = (
            mask
            & (p95_cpu <= max_p95_cpu)
        )

    candidates = (
        result.loc[mask]
        .sort_values(
            "_estimated_total_cost",
            ascending=False,
        )
        .head(limit)
    )

    rows: list[dict[str, Any]] = []

    for index, row in candidates.iterrows():
        estimated_cost = float(
            row["_estimated_total_cost"]
        )

        potential_saving = (
            estimated_cost * 0.5
        )

        rows.append(
            {
                "vm_id": (
                    str(row[vm_id_col])
                    if vm_id_col
                    else str(index)
                ),
                "avg_cpu": round(
                    float(row[avg_cpu_col]),
                    2,
                ),
                "p95_cpu": round(
                    float(row[p95_cpu_col]),
                    2,
                )
                if p95_cpu_col
                else None,
                "cores": round(
                    float(row[cores_col]),
                    2,
                ),
                "lifetime_hours": round(
                    float(row[lifetime_col]),
                    2,
                ),
                "estimated_cost_usd": round(
                    estimated_cost,
                    2,
                ),
                "estimated_potential_saving_usd": round(
                    potential_saving,
                    2,
                ),
                "recommendation": (
                    "Review for downsizing or shutdown"
                ),
                "confidence": (
                    "high"
                    if float(row[avg_cpu_col]) <= 5
                    else "medium"
                ),
            }
        )

    return rows