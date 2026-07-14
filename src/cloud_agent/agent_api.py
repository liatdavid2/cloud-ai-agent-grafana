from __future__ import annotations

import html
import os

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .settings import settings

import html
import json
import os

import httpx
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI

app = FastAPI(
    title="Azure Cloud AI Agent",
    version="1.1.0",
    description="An OpenAI Agent that investigates the Azure trace through MCP tools.",
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    model: str


INSTRUCTIONS = """
You are an Azure cloud reliability and capacity analyst.
Always use the MCP tools before making data claims.
Separate your response into Evidence, Interpretation, Recommendation, and Limitations.
Do not invent prices, Azure regions, application logs, root causes, or time-series behavior that
is not present in the dataset. Explain that this public trace is anonymized when relevant.
Prefer concise, actionable answers and include the thresholds used.
""".strip()

PANEL_PROMPTS = {
    "overview": "Explain the overall cloud dashboard using get_cloud_overview.",
    "categories": "Explain the VM categories panel using summarize_vm_categories.",
    "deployments": "Explain the largest deployments panel using get_largest_deployments.",
    "high-cpu": "Explain the highest average CPU panel using find_overloaded_vms.",
    "underutilized": "Explain the underutilized VMs panel using find_underutilized_vms.",
    "rightsizing": "Explain the rightsizing candidates panel using recommend_rightsizing.",
    "anomalies": "Explain the CPU anomalies panel using detect_cpu_anomalies.",
}


async def run_agent(question: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in .env to run AI explanations.",
        )

    async with MCPServerStreamableHttp(
        name="Azure Cloud MCP",
        params={"url": settings.mcp_url, "timeout": 30},
        cache_tools_list=True,
        max_retry_attempts=2,
    ) as server:
        agent = Agent(
            name="Azure Cloud Reliability Agent",
            instructions=INSTRUCTIONS,
            model=settings.openai_model,
            mcp_servers=[server],
            mcp_config={"convert_schemas_to_strict": True},
        )
        result = await Runner.run(agent, question)
        return str(result.final_output)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "mcp_url": settings.mcp_url,
        "model": settings.openai_model,
    }


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    answer = await run_agent(request.question)
    return AskResponse(answer=answer, model=settings.openai_model)


@app.get("/explain/{panel_key}", response_class=HTMLResponse)
async def explain_panel(panel_key: str) -> HTMLResponse:
    prompt = PANEL_PROMPTS.get(panel_key)
    if prompt is None:
        raise HTTPException(status_code=404, detail=f"Unknown panel: {panel_key}")

    answer = await run_agent(
        f"{prompt}\n"
        "Keep the explanation concise and explicitly separate Evidence, Interpretation, "
        "Recommendation, and Limitations."
    )

    safe_answer = html.escape(answer).replace("\n", "<br>")
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <title>AI explanation: {html.escape(panel_key)}</title>
          </head>
          <body style="font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.6;padding:0 20px">
            <h1>AI explanation</h1>
            <p><strong>Panel:</strong> {html.escape(panel_key)}</p>
            <div>{safe_answer}</div>
            <p style="margin-top:30px"><a href="http://localhost:3000">Back to Grafana</a></p>
          </body>
        </html>
        """
    )
