from __future__ import annotations

from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from .analytics import (
    category_summary,
    cpu_anomalies,
    dataset_summary,
    deployment_summary,
    high_cpu_vms,
    kpis,
    rightsizing_candidates,
    underutilized_vms,
)
from .dataset import load_dataset
from .settings import settings

from cloud_agent.advisor import (
    advisor_summary,
    deployment_advisor_summary,
    generate_advisor_recommendations,
)

from cloud_agent.cost_estimator import (
    estimate_monthly_cost,
    estimate_vm_costs,
    estimate_deployment_costs,
    find_expensive_underutilized_vms,
)

frame: pd.DataFrame | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global frame
    frame = load_dataset(settings.dataset_path)
    yield


app = FastAPI(
    title="Azure Cloud Analytics API",
    version="2.0.0",
    description="JSON analytics over a local 10,000-row subset of the real Azure VM trace.",
    lifespan=lifespan,
)


def data() -> pd.DataFrame:
    if frame is None:
        raise HTTPException(status_code=503, detail="Dataset is not loaded")
    return frame


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "dataset_loaded": frame is not None, "dataset_path": str(settings.dataset_path)}


@app.get("/summary")
def summary() -> dict:
    return dataset_summary(data())


@app.get("/kpis")
def dashboard_kpis() -> list[dict]:
    return [kpis(data())]


@app.get("/categories")
def categories() -> list[dict]:
    return category_summary(data())


@app.get("/deployments")
def deployments(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    return deployment_summary(data(), limit=limit)


@app.get("/high-cpu")
def high_cpu(
    threshold: float = Query(80, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    return high_cpu_vms(data(), threshold=threshold, limit=limit)


@app.get("/underutilized")
def underutilized(
    threshold: float = Query(10, ge=0, le=100),
    min_lifetime_hours: float = Query(24, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    return underutilized_vms(data(), threshold, min_lifetime_hours, limit)


@app.get("/rightsizing")
def rightsizing(
    max_avg_cpu: float = Query(20, ge=0, le=100),
    max_p95_cpu: float = Query(40, ge=0, le=100),
    min_cores: int = Query(2, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    return rightsizing_candidates(data(), max_avg_cpu, max_p95_cpu, min_cores, limit)


@app.get("/anomalies")
def anomalies(
    z_threshold: float = Query(3.0, ge=0.5, le=10),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    return cpu_anomalies(data(), z_threshold, limit)


@app.get("/advisor/summary")
def advisor():
    return advisor_summary()


@app.get("/advisor/deployments")
def advisor_deployments():
    return deployment_advisor_summary()

@app.get("/advisor/recommendations")
def advisor_recommendations():
    return generate_advisor_recommendations()

@app.get("/cost/monthly")
def monthly():
    return estimate_monthly_cost()


@app.get("/cost/vms")
def vm_cost():
    return estimate_vm_costs()

@app.get("/cost/deployments")
def deployment_cost():
    return estimate_deployment_costs()

@app.get("/cost/underutilized")
def expensive():
    return find_expensive_underutilized_vms()