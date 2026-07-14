import pandas as pd

from src.cloud_agent.analytics import (
    category_summary,
    cpu_anomalies,
    dataset_summary,
    high_cpu_vms,
    kpis,
    rightsizing_candidates,
    short_id,
    underutilized_vms,
)


def sample_frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            ["vm-a", "sub-1", "dep-1", 0, 360000, 12, 4, 8, "Delay-insensitive", 4, 16],
            ["vm-b", "sub-1", "dep-1", 0, 7200, 100, 90, 98, "Interactive", 2, 8],
            ["vm-c", "sub-2", "dep-2", 0, 720000, 20, 5, 10, "Delay-insensitive", 8, 32],
            ["vm-d", "sub-2", "dep-3", 0, 18000, 60, 30, 55, "Interactive", 1, 2],
        ],
        columns=[
            "vmid", "subscriptionid", "deploymentid", "vmcreated", "vmdeleted",
            "maxcpu", "avgcpu", "p95maxcpu", "vmcategory", "vmcorecount", "vmmemory",
        ],
    )
    frame["lifetime_hours"] = (frame["vmdeleted"] - frame["vmcreated"]) / 3600
    frame["core_hours"] = frame["lifetime_hours"] * frame["vmcorecount"]
    return frame


def test_summary_and_kpis() -> None:
    summary = dataset_summary(sample_frame())
    assert summary["rows"] == 4
    assert summary["subscriptions"] == 2
    assert kpis(sample_frame())["high_cpu_vms"] == 1


def test_high_low_and_rightsizing() -> None:
    high = high_cpu_vms(sample_frame(), threshold=80)
    low = underutilized_vms(sample_frame(), threshold=10, min_lifetime_hours=24)
    rightsizing = rightsizing_candidates(sample_frame(), max_avg_cpu=10, max_p95_cpu=20)
    assert high[0]["vm_id"] == short_id("vm-b")
    assert {item["vm_id"] for item in low} == {short_id("vm-a"), short_id("vm-c")}
    assert rightsizing[0]["potential_core_reduction"] >= 1


def test_categories_and_anomalies() -> None:
    assert len(category_summary(sample_frame())) == 2
    assert isinstance(cpu_anomalies(sample_frame(), z_threshold=1.0), list)
