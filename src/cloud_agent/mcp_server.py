from __future__ import annotations

import os
from typing import Any

import requests
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

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")
GRAFANA_DASHBOARD_UID = os.getenv("GRAFANA_DASHBOARD_UID", "azure-cloud-ai-agent")


def grafana_request(method: str, path: str, **kwargs: Any) -> dict:
    response = requests.request(
        method,
        f"{GRAFANA_URL}{path}",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json() if response.content else {}


def load_dashboard(uid: str) -> dict:
    return grafana_request("GET", f"/api/dashboards/uid/{uid}")


def save_dashboard(dashboard: dict, message: str) -> dict:
    dashboard.pop("id", None)
    return grafana_request(
        "POST",
        "/api/dashboards/db",
        json={"dashboard": dashboard, "overwrite": True, "message": message},
    )


def find_panel(dashboard: dict, panel_title: str) -> dict:
    for panel in dashboard.get("panels", []):
        if panel.get("title") == panel_title:
            return panel
    raise ValueError(f"Panel not found: {panel_title}")


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


@mcp.tool()
def list_grafana_panels(uid: str = GRAFANA_DASHBOARD_UID) -> list[dict]:
    """List the titles and visualization types of panels in the Grafana dashboard."""
    dashboard = load_dashboard(uid)["dashboard"]
    return [
        {"id": panel.get("id"), "title": panel.get("title"), "type": panel.get("type")}
        for panel in dashboard.get("panels", [])
    ]


@mcp.tool()
def change_panel_visualization(
    panel_title: str,
    visualization: str,
    uid: str = GRAFANA_DASHBOARD_UID,
) -> dict:
    """Change a Grafana panel type. Supported: table, stat, gauge, timeseries, barchart, piechart."""
    allowed = {"table", "stat", "gauge", "timeseries", "barchart", "piechart"}
    if visualization not in allowed:
        raise ValueError(f"visualization must be one of {sorted(allowed)}")

    payload = load_dashboard(uid)
    dashboard = payload["dashboard"]
    panel = find_panel(dashboard, panel_title)
    old_type = panel.get("type")
    panel["type"] = visualization
    result = save_dashboard(
        dashboard,
        f"MCP changed {panel_title} from {old_type} to {visualization}",
    )
    return {
        "status": "updated",
        "panel": panel_title,
        "old_type": old_type,
        "new_type": visualization,
        "grafana": result,
    }


@mcp.tool()
def rename_grafana_panel(
    panel_title: str,
    new_title: str,
    uid: str = GRAFANA_DASHBOARD_UID,
) -> dict:
    """Rename a Grafana dashboard panel."""
    payload = load_dashboard(uid)
    dashboard = payload["dashboard"]
    panel = find_panel(dashboard, panel_title)
    panel["title"] = new_title
    result = save_dashboard(dashboard, f"MCP renamed {panel_title} to {new_title}")
    return {
        "status": "updated",
        "old_title": panel_title,
        "new_title": new_title,
        "grafana": result,
    }


if __name__ == "__main__":
    transport = os.getenv(
        "MCP_TRANSPORT",
        "streamable-http",
    )

    mcp.run(transport=transport)
