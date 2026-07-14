from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    dataset_path: Path = Path(os.getenv("DATASET_PATH", "data/azure_vm_usage_10000.csv"))
    mcp_url: str = os.getenv("MCP_URL", "http://localhost:8002/mcp")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")


settings = Settings()
