from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from .cost_estimator import (
    DEFAULT_PRICE_PER_CORE_HOUR,
    DEFAULT_PRICE_PER_GB_HOUR,
    _find_column,
    _prepare_cost_frame,
    _safe_numeric,
)


def _severity_rank(
    severity: str,
) -> int:
    order = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
        "info": 0,
    }

    return order.get(
        severity.lower(),
        0,
    )


def _recommendation_priority(
    estimated_saving: float,
    severity: str,
) -> float:
    return (
        estimated_saving
        + (_severity_rank(severity) * 1000)
    )


def generate_advisor_recommendations(
    frame: pd.DataFrame,
    limit: int = 50,
    low_cpu_threshold: float = 10,
    very_low_cpu_threshold: float = 5,
    high_cpu_threshold: float = 80,
    critical_cpu_threshold: float = 90,
    low_p95_threshold: float = 20,
    high_p95_threshold: float = 85,
    long_running_hours: float = 720,
    min_cores_for_downsize: int = 2,
    price_per_core_hour: float = DEFAULT_PRICE_PER_CORE_HOUR,
    price_per_gb_hour: float = DEFAULT_PRICE_PER_GB_HOUR,
) -> list[dict[str, Any]]:
    """
    Generate Azure Advisor-style recommendations.

    These recommendations are heuristic and evidence-based.
    They do not call the real Azure Advisor service.
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

    deployment_col = _find_column(
        result,
        "deployment_id",
        required=False,
    )

    avg_cpu_col = _find_column(
        result,
        "avg_cpu",
    )

    p95_cpu_col = _find_column(
        result,
        "p95_cpu",
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

    recommendations: list[dict[str, Any]] = []

    for index, row in result.iterrows():
        vm_id = (
            str(row[vm_id_col])
            if vm_id_col
            else str(index)
        )

        deployment_id = (
            str(row[deployment_col])
            if deployment_col
            else None
        )

        avg_cpu = float(
            row[avg_cpu_col]
        )

        p95_cpu = (
            float(row[p95_cpu_col])
            if p95_cpu_col
            else avg_cpu
        )

        cores = float(
            row[cores_col]
        )

        memory_gb = (
            float(row[memory_col])
            if memory_col
            else None
        )

        lifetime_hours = float(
            row[lifetime_col]
        )

        estimated_cost = float(
            row["_estimated_total_cost"]
        )

        if (
            avg_cpu <= very_low_cpu_threshold
            and p95_cpu <= low_p95_threshold
            and lifetime_hours >= 24
        ):
            estimated_saving = (
                estimated_cost * 0.75
            )

            recommendations.append(
                {
                    "vm_id": vm_id,
                    "deployment_id": deployment_id,
                    "category": "cost",
                    "recommendation_type": (
                        "shutdown_or_aggressive_downsize"
                    ),
                    "severity": "high",
                    "title": (
                        "VM appears severely underutilized"
                    ),
                    "evidence": {
                        "avg_cpu": round(avg_cpu, 2),
                        "p95_cpu": round(p95_cpu, 2),
                        "cores": round(cores, 2),
                        "lifetime_hours": round(
                            lifetime_hours,
                            2,
                        ),
                    },
                    "recommendation": (
                        "Review whether the VM can be "
                        "stopped, consolidated, or reduced "
                        "to a substantially smaller size."
                    ),
                    "estimated_current_cost_usd": round(
                        estimated_cost,
                        2,
                    ),
                    "estimated_potential_saving_usd": round(
                        estimated_saving,
                        2,
                    ),
                    "confidence": "high",
                    "limitation": (
                        "The dataset does not contain "
                        "business criticality, SLA, or "
                        "application dependency information."
                    ),
                }
            )

        elif (
            avg_cpu <= low_cpu_threshold
            and p95_cpu <= low_p95_threshold
            and cores >= min_cores_for_downsize
            and lifetime_hours >= 24
        ):
            estimated_saving = (
                estimated_cost * 0.5
            )

            recommendations.append(
                {
                    "vm_id": vm_id,
                    "deployment_id": deployment_id,
                    "category": "cost",
                    "recommendation_type": (
                        "rightsize_down"
                    ),
                    "severity": "medium",
                    "title": (
                        "VM is a rightsizing candidate"
                    ),
                    "evidence": {
                        "avg_cpu": round(avg_cpu, 2),
                        "p95_cpu": round(p95_cpu, 2),
                        "cores": round(cores, 2),
                        "lifetime_hours": round(
                            lifetime_hours,
                            2,
                        ),
                    },
                    "recommendation": (
                        "Consider reducing the allocated "
                        "core count by approximately 50% "
                        "and monitor performance."
                    ),
                    "estimated_current_cost_usd": round(
                        estimated_cost,
                        2,
                    ),
                    "estimated_potential_saving_usd": round(
                        estimated_saving,
                        2,
                    ),
                    "confidence": "medium",
                    "limitation": (
                        "The recommendation is based on CPU "
                        "utilization and does not include "
                        "application-level latency."
                    ),
                }
            )

        if (
            avg_cpu >= critical_cpu_threshold
            or p95_cpu >= 95
        ):
            recommendations.append(
                {
                    "vm_id": vm_id,
                    "deployment_id": deployment_id,
                    "category": "performance",
                    "recommendation_type": (
                        "scale_up_or_scale_out"
                    ),
                    "severity": "critical",
                    "title": (
                        "VM is at critical CPU pressure"
                    ),
                    "evidence": {
                        "avg_cpu": round(avg_cpu, 2),
                        "p95_cpu": round(p95_cpu, 2),
                        "cores": round(cores, 2),
                    },
                    "recommendation": (
                        "Investigate sustained CPU pressure. "
                        "Consider scaling up, scaling out, "
                        "or redistributing the workload."
                    ),
                    "estimated_current_cost_usd": round(
                        estimated_cost,
                        2,
                    ),
                    "estimated_potential_saving_usd": 0.0,
                    "confidence": "high",
                    "limitation": (
                        "The dataset does not identify the "
                        "application-level root cause."
                    ),
                }
            )

        elif (
            avg_cpu >= high_cpu_threshold
            or p95_cpu >= high_p95_threshold
        ):
            recommendations.append(
                {
                    "vm_id": vm_id,
                    "deployment_id": deployment_id,
                    "category": "performance",
                    "recommendation_type": (
                        "capacity_review"
                    ),
                    "severity": "high",
                    "title": (
                        "VM has elevated CPU utilization"
                    ),
                    "evidence": {
                        "avg_cpu": round(avg_cpu, 2),
                        "p95_cpu": round(p95_cpu, 2),
                        "cores": round(cores, 2),
                    },
                    "recommendation": (
                        "Review capacity and determine "
                        "whether the workload is persistently "
                        "or only intermittently constrained."
                    ),
                    "estimated_current_cost_usd": round(
                        estimated_cost,
                        2,
                    ),
                    "estimated_potential_saving_usd": 0.0,
                    "confidence": "medium",
                    "limitation": (
                        "A high P95 value may reflect short "
                        "bursts rather than sustained pressure."
                    ),
                }
            )

        cpu_gap = (
            p95_cpu
            - avg_cpu
        )

        if (
            cpu_gap >= 50
            and p95_cpu >= 70
        ):
            recommendations.append(
                {
                    "vm_id": vm_id,
                    "deployment_id": deployment_id,
                    "category": "reliability",
                    "recommendation_type": (
                        "bursty_workload_review"
                    ),
                    "severity": "medium",
                    "title": (
                        "VM shows bursty CPU behavior"
                    ),
                    "evidence": {
                        "avg_cpu": round(avg_cpu, 2),
                        "p95_cpu": round(p95_cpu, 2),
                        "cpu_gap": round(cpu_gap, 2),
                    },
                    "recommendation": (
                        "Review autoscaling, queueing, "
                        "or workload scheduling strategies "
                        "for short utilization spikes."
                    ),
                    "estimated_current_cost_usd": round(
                        estimated_cost,
                        2,
                    ),
                    "estimated_potential_saving_usd": 0.0,
                    "confidence": "medium",
                    "limitation": (
                        "The trace does not include request "
                        "latency or autoscaling events."
                    ),
                }
            )

        if (
            lifetime_hours >= long_running_hours
            and avg_cpu <= 20
        ):
            estimated_saving = (
                estimated_cost * 0.25
            )

            recommendations.append(
                {
                    "vm_id": vm_id,
                    "deployment_id": deployment_id,
                    "category": "governance",
                    "recommendation_type": (
                        "review_long_running_resource"
                    ),
                    "severity": "low",
                    "title": (
                        "Long-running VM should be reviewed"
                    ),
                    "evidence": {
                        "avg_cpu": round(avg_cpu, 2),
                        "lifetime_hours": round(
                            lifetime_hours,
                            2,
                        ),
                        "cores": round(cores, 2),
                        "memory_gb": (
                            round(memory_gb, 2)
                            if memory_gb is not None
                            else None
                        ),
                    },
                    "recommendation": (
                        "Confirm that this long-running VM "
                        "is still required and assigned to "
                        "an active workload owner."
                    ),
                    "estimated_current_cost_usd": round(
                        estimated_cost,
                        2,
                    ),
                    "estimated_potential_saving_usd": round(
                        estimated_saving,
                        2,
                    ),
                    "confidence": "low",
                    "limitation": (
                        "Long runtime alone does not indicate "
                        "that a VM is unnecessary."
                    ),
                }
            )

    for recommendation in recommendations:
        recommendation["_priority"] = (
            _recommendation_priority(
                estimated_saving=float(
                    recommendation.get(
                        "estimated_potential_saving_usd",
                        0.0,
                    )
                ),
                severity=str(
                    recommendation.get(
                        "severity",
                        "info",
                    )
                ),
            )
        )

    recommendations.sort(
        key=lambda item: item["_priority"],
        reverse=True,
    )

    output = recommendations[:limit]

    for recommendation in output:
        recommendation.pop(
            "_priority",
            None,
        )

    return output


def advisor_summary(
    frame: pd.DataFrame,
    recommendation_limit: int = 500,
) -> dict[str, Any]:
    """
    Return a high-level summary of Advisor recommendations.
    """

    recommendations = generate_advisor_recommendations(
        frame=frame,
        limit=recommendation_limit,
    )

    if not recommendations:
        return {
            "total_recommendations": 0,
            "estimated_potential_saving_usd": 0.0,
            "by_severity": {},
            "by_category": {},
            "by_type": {},
        }

    severity_counts = Counter(
        recommendation["severity"]
        for recommendation in recommendations
    )

    category_counts = Counter(
        recommendation["category"]
        for recommendation in recommendations
    )

    type_counts = Counter(
        recommendation[
            "recommendation_type"
        ]
        for recommendation in recommendations
    )

    total_saving = sum(
        float(
            recommendation.get(
                "estimated_potential_saving_usd",
                0.0,
            )
        )
        for recommendation in recommendations
    )

    affected_vms = {
        recommendation["vm_id"]
        for recommendation in recommendations
    }

    return {
        "total_recommendations": len(
            recommendations
        ),
        "affected_vms": len(
            affected_vms
        ),
        "estimated_potential_saving_usd": round(
            total_saving,
            2,
        ),
        "by_severity": dict(
            severity_counts
        ),
        "by_category": dict(
            category_counts
        ),
        "by_type": dict(
            type_counts
        ),
        "important_note": (
            "Recommendations and savings are heuristic "
            "estimates based on the trace dataset. "
            "They are not output from the official "
            "Azure Advisor service."
        ),
    }


def deployment_advisor_summary(
    frame: pd.DataFrame,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Aggregate recommendations and potential savings
    by deployment.
    """

    recommendations = generate_advisor_recommendations(
        frame=frame,
        limit=max(
            500,
            limit * 20,
        ),
    )

    grouped: dict[str, dict[str, Any]] = {}

    for recommendation in recommendations:
        deployment_id = (
            recommendation.get(
                "deployment_id"
            )
            or "unknown"
        )

        current = grouped.setdefault(
            deployment_id,
            {
                "deployment_id": deployment_id,
                "recommendation_count": 0,
                "affected_vms": set(),
                "estimated_potential_saving_usd": 0.0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
            },
        )

        current[
            "recommendation_count"
        ] += 1

        current["affected_vms"].add(
            recommendation["vm_id"]
        )

        current[
            "estimated_potential_saving_usd"
        ] += float(
            recommendation.get(
                "estimated_potential_saving_usd",
                0.0,
            )
        )

        severity = recommendation.get(
            "severity",
            "low",
        )

        severity_key = (
            f"{severity}_count"
        )

        if severity_key in current:
            current[severity_key] += 1

    rows: list[dict[str, Any]] = []

    for item in grouped.values():
        rows.append(
            {
                "deployment_id": item[
                    "deployment_id"
                ],
                "recommendation_count": item[
                    "recommendation_count"
                ],
                "affected_vms": len(
                    item["affected_vms"]
                ),
                "estimated_potential_saving_usd": round(
                    item[
                        "estimated_potential_saving_usd"
                    ],
                    2,
                ),
                "critical_count": item[
                    "critical_count"
                ],
                "high_count": item[
                    "high_count"
                ],
                "medium_count": item[
                    "medium_count"
                ],
                "low_count": item[
                    "low_count"
                ],
            }
        )

    rows.sort(
        key=lambda item: (
            item["critical_count"],
            item["high_count"],
            item[
                "estimated_potential_saving_usd"
            ],
        ),
        reverse=True,
    )

    return rows[:limit]