from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import requests
from mcp.server.fastmcp import FastMCP
import copy
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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

GRAFANA_URL = os.getenv(
    "GRAFANA_URL",
    "http://grafana:3000",
)

GRAFANA_USER = os.getenv(
    "GRAFANA_ADMIN_USER",
    "admin",
)

GRAFANA_PASSWORD = os.getenv(
    "GRAFANA_ADMIN_PASSWORD",
    "admin",
)

GRAFANA_DASHBOARD_UID = os.getenv(
    "GRAFANA_DASHBOARD_UID",
    "azure-cloud-ai-agent",
)

ANALYTICS_API_URL = os.getenv(
    "ANALYTICS_API_URL",
    "http://api:8000",
)

ALLOWED_VISUALIZATIONS = {
    "table",
    "stat",
    "gauge",
    "timeseries",
    "barchart",
    "piechart",
}

AVAILABLE_DATASETS = {
    "high_cpu": "/high-cpu",
    "underutilized": "/underutilized",
    "rightsizing": "/rightsizing",
    "deployments": "/deployments",
    "categories": "/categories",
    "anomalies": "/anomalies",
}


def grafana_request(
    method: str,
    path: str,
    **kwargs: Any,
) -> dict:
    response = requests.request(
        method,
        f"{GRAFANA_URL}{path}",
        auth=(
            GRAFANA_USER,
            GRAFANA_PASSWORD,
        ),
        timeout=30,
        **kwargs,
    )

    response.raise_for_status()

    return (
        response.json()
        if response.content
        else {}
    )


def load_dashboard(uid: str) -> dict:
    return grafana_request(
        "GET",
        f"/api/dashboards/uid/{uid}",
    )


def save_dashboard(
    dashboard: dict,
    message: str,
) -> dict:
    dashboard.pop("id", None)

    return grafana_request(
        "POST",
        "/api/dashboards/db",
        json={
            "dashboard": dashboard,
            "overwrite": True,
            "message": message,
        },
    )


def find_panel(
    dashboard: dict,
    panel_title: str | None = None,
    panel_id: int | None = None,
) -> dict:
    panels = dashboard.get("panels", [])

    if panel_id is not None:
        for panel in panels:
            if panel.get("id") == panel_id:
                return panel

        raise ValueError(
            f"Panel not found by id: {panel_id}"
        )

    if panel_title is not None:
        matches = [
            panel
            for panel in panels
            if panel.get("title") == panel_title
        ]

        if not matches:
            raise ValueError(
                f"Panel not found: {panel_title}"
            )

        if len(matches) > 1:
            panel_ids = [
                panel.get("id")
                for panel in matches
            ]

            raise ValueError(
                f"Multiple panels found with title "
                f"'{panel_title}'. "
                f"Use panel_id instead. "
                f"Matching ids: {panel_ids}"
            )

        return matches[0]

    raise ValueError(
        "Provide panel_title or panel_id"
    )


def build_dataset_url(
    dataset: str,
    filters: dict[str, Any] | None,
    limit: int,
) -> str:
    endpoint = AVAILABLE_DATASETS.get(dataset)

    if endpoint is None:
        raise ValueError(
            f"dataset must be one of "
            f"{sorted(AVAILABLE_DATASETS)}"
        )

    params: dict[str, Any] = {}

    if dataset not in {
        "categories",
    }:
        params["limit"] = limit

    if filters:
        params.update(filters)

    query = urlencode(
        params,
        doseq=True,
    )

    url = f"{ANALYTICS_API_URL}{endpoint}"

    if query:
        url = f"{url}?{query}"

    return url


@mcp.tool()
def get_cloud_overview() -> dict:
    """
    Return the size and main utilization statistics
    of the Azure VM subset.
    """
    return dataset_summary(frame)


@mcp.tool()
def find_overloaded_vms(
    threshold: float = 80,
    limit: int = 20,
) -> list[dict]:
    """
    Find VMs whose mean CPU is at or above
    the requested threshold.
    """
    return high_cpu_vms(
        frame,
        threshold,
        limit,
    )


@mcp.tool()
def find_underutilized_vms(
    threshold: float = 10,
    min_lifetime_hours: float = 24,
    limit: int = 20,
) -> list[dict]:
    """
    Find long-running VMs with consistently
    low mean and P95 CPU.
    """
    return underutilized_vms(
        frame,
        threshold,
        min_lifetime_hours,
        limit,
    )


@mcp.tool()
def recommend_rightsizing(
    max_avg_cpu: float = 20,
    max_p95_cpu: float = 40,
    min_cores: int = 2,
    limit: int = 20,
) -> list[dict]:
    """
    Return conservative CPU rightsizing candidates
    without inventing prices.
    """
    return rightsizing_candidates(
        frame,
        max_avg_cpu,
        max_p95_cpu,
        min_cores,
        limit,
    )


@mcp.tool()
def detect_cpu_anomalies(
    z_threshold: float = 3.0,
    limit: int = 20,
) -> list[dict]:
    """
    Detect unusually high or low average CPU values
    using a z-score.
    """
    return cpu_anomalies(
        frame,
        z_threshold,
        limit,
    )


@mcp.tool()
def summarize_vm_categories() -> list[dict]:
    """
    Compare VM categories by CPU, cores, memory,
    VM count, and core-hours.
    """
    return category_summary(frame)


@mcp.tool()
def get_largest_deployments(
    limit: int = 20,
) -> list[dict]:
    """
    Find deployments with the largest total
    core-hour footprint.
    """
    return deployment_summary(
        frame,
        limit,
    )


@mcp.tool()
def list_grafana_panels(
    uid: str = GRAFANA_DASHBOARD_UID,
) -> list[dict]:
    """
    List panel ids, titles and visualization types
    in the Grafana dashboard.
    """
    dashboard = load_dashboard(uid)["dashboard"]

    return [
        {
            "id": panel.get("id"),
            "title": panel.get("title"),
            "type": panel.get("type"),
        }
        for panel in dashboard.get("panels", [])
    ]


@mcp.tool()
def change_panel_visualization(
    visualization: str,
    panel_title: str | None = None,
    panel_id: int | None = None,
    uid: str = GRAFANA_DASHBOARD_UID,
) -> dict:
    """
    Change a Grafana panel visualization.

    Use panel_id when multiple panels share
    the same title.

    Supported visualization values:
    table, stat, gauge, timeseries,
    barchart and piechart.
    """

    if visualization not in ALLOWED_VISUALIZATIONS:
        raise ValueError(
            f"visualization must be one of "
            f"{sorted(ALLOWED_VISUALIZATIONS)}"
        )

    payload = load_dashboard(uid)
    dashboard = payload["dashboard"]

    panel = find_panel(
        dashboard=dashboard,
        panel_title=panel_title,
        panel_id=panel_id,
    )

    old_type = panel.get("type")
    panel["type"] = visualization

    result = save_dashboard(
        dashboard,
        (
            f"MCP changed panel "
            f"{panel.get('id')} "
            f"from {old_type} "
            f"to {visualization}"
        ),
    )

    return {
        "status": "updated",
        "panel_id": panel.get("id"),
        "panel": panel.get("title"),
        "old_type": old_type,
        "new_type": visualization,
        "grafana": result,
    }


@mcp.tool()
def rename_grafana_panel(
    new_title: str,
    panel_title: str | None = None,
    panel_id: int | None = None,
    uid: str = GRAFANA_DASHBOARD_UID,
) -> dict:
    """
    Rename a Grafana dashboard panel.

    Use panel_id when multiple panels share
    the same title.
    """

    payload = load_dashboard(uid)
    dashboard = payload["dashboard"]

    panel = find_panel(
        dashboard=dashboard,
        panel_title=panel_title,
        panel_id=panel_id,
    )

    old_title = panel.get("title")
    panel["title"] = new_title

    result = save_dashboard(
        dashboard,
        (
            f"MCP renamed panel "
            f"{panel.get('id')} "
            f"from {old_title} "
            f"to {new_title}"
        ),
    )

    return {
        "status": "updated",
        "panel_id": panel.get("id"),
        "old_title": old_title,
        "new_title": new_title,
        "grafana": result,
    }


@mcp.tool()
def create_dashboard_panel(
    source_panel_id: int,
    title: str,
    visualization: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
    uid: str = GRAFANA_DASHBOARD_UID,
) -> dict:
    """
    Create a new Grafana panel by duplicating an existing panel.

    The user describes the request in natural language.
    Claude should:
    1. Call list_grafana_panels to find the source panel ID.
    2. Pass that ID as source_panel_id.
    3. Translate requested filters into structured filter values.

    Examples:
    - Duplicate the Underutilized VMs table and show only VMs
      running longer than 48 hours.
    - Duplicate the Highest Average CPU panel and show only
      the top 10 results.
    - Duplicate panel 9 and display it as a bar chart.

    Supported visualization values:
    table, stat, gauge, timeseries, barchart and piechart.

    filters are added to or replace the query parameters
    of the existing panel URL.
    """

    if (
        visualization is not None
        and visualization not in ALLOWED_VISUALIZATIONS
    ):
        raise ValueError(
            f"visualization must be one of "
            f"{sorted(ALLOWED_VISUALIZATIONS)}"
        )

    payload = load_dashboard(uid)
    dashboard = payload["dashboard"]
    panels = dashboard.setdefault("panels", [])

    source_panel = find_panel(
        dashboard=dashboard,
        panel_id=source_panel_id,
    )

    if not source_panel.get("targets"):
        raise ValueError(
            f"Source panel {source_panel_id} has no query target"
        )

    source_url = source_panel["targets"][0].get("url")

    if not source_url:
        raise ValueError(
            f"Source panel {source_panel_id} has no API URL"
        )

    new_panel = copy.deepcopy(source_panel)

    next_id = (
        max(
            [panel.get("id", 0) for panel in panels]
            + [0]
        )
        + 1
    )

    next_y = max(
        [
            panel.get("gridPos", {}).get("y", 0)
            + panel.get("gridPos", {}).get("h", 0)
            for panel in panels
        ]
        + [0]
    )

    new_panel["id"] = next_id
    new_panel["title"] = title

    new_panel["gridPos"] = {
        "x": 0,
        "y": next_y,
        "w": source_panel.get(
            "gridPos",
            {},
        ).get("w", 12),
        "h": source_panel.get(
            "gridPos",
            {},
        ).get("h", 8),
    }

    if visualization is not None:
        new_panel["type"] = visualization

    parsed_url = urlparse(source_url)
    query_params = parse_qs(
        parsed_url.query,
        keep_blank_values=True,
    )

    if filters:
        for key, value in filters.items():
            if value is None:
                query_params.pop(key, None)
            elif isinstance(value, list):
                query_params[key] = [
                    str(item)
                    for item in value
                ]
            else:
                query_params[key] = [str(value)]

    if limit is not None:
        query_params["limit"] = [str(limit)]

    new_query = urlencode(
        query_params,
        doseq=True,
    )

    new_url = urlunparse(
        parsed_url._replace(
            query=new_query,
        )
    )

    for target in new_panel.get("targets", []):
        if target.get("url"):
            target["url"] = new_url

    panels.append(new_panel)

    result = save_dashboard(
        dashboard,
        (
            f"MCP duplicated panel {source_panel_id} "
            f"as '{title}'"
        ),
    )

    return {
        "status": "created",
        "source_panel_id": source_panel_id,
        "panel_id": next_id,
        "title": title,
        "visualization": new_panel.get("type"),
        "filters": filters or {},
        "limit": limit,
        "url": new_url,
        "grafana": result,
    }


if __name__ == "__main__":
    transport = os.getenv(
        "MCP_TRANSPORT",
        "streamable-http",
    )

    mcp.run(
        transport=transport,
    )