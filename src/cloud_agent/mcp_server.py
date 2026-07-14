from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from .analytics import (
    category_summary,
    cpu_anomalies,
    dataset_summary,
    deployment_summary,
    high_cpu_vms,
    rightsizing_candidates,
    underutilized_vms,
)
from .dataset import load_dataset
from .settings import settings

frame = load_dataset(settings.dataset_path)

mcp = FastMCP(
    "Azure Cloud Reliability Tools",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    json_response=True,
    stateless_http=True,
)


@mcp.tool()
def get_cloud_overview() -> dict:
    """Return the size and main utilization statistics of the Azure VM subset."""
    return dataset_summary(frame)


@mcp.tool()
def find_overloaded_vms(threshold: float = 80, limit: int = 20) -> list[dict]:
    """Find VMs whose mean CPU is at or above the requested threshold."""
    return high_cpu_vms(frame, threshold, limit)


@mcp.tool()
def find_underutilized_vms(
    threshold: float = 10,
    min_lifetime_hours: float = 24,
    limit: int = 20,
) -> list[dict]:
    """Find long-running VMs with consistently low mean and P95 CPU."""
    return underutilized_vms(frame, threshold, min_lifetime_hours, limit)


@mcp.tool()
def recommend_rightsizing(
    max_avg_cpu: float = 20,
    max_p95_cpu: float = 40,
    min_cores: int = 2,
    limit: int = 20,
) -> list[dict]:
    """Return conservative CPU rightsizing candidates without inventing prices."""
    return rightsizing_candidates(frame, max_avg_cpu, max_p95_cpu, min_cores, limit)


@mcp.tool()
def detect_cpu_anomalies(z_threshold: float = 3.0, limit: int = 20) -> list[dict]:
    """Detect unusually high or low average CPU values using a z-score."""
    return cpu_anomalies(frame, z_threshold, limit)


@mcp.tool()
def summarize_vm_categories() -> list[dict]:
    """Compare VM categories by CPU, cores, memory, VM count, and core-hours."""
    return category_summary(frame)


@mcp.tool()
def get_largest_deployments(limit: int = 20) -> list[dict]:
    """Find deployments with the largest total core-hour footprint."""
    return deployment_summary(frame, limit)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
