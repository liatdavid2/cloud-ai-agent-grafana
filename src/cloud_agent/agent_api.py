from __future__ import annotations

import os

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .settings import settings

app = FastAPI(
    title="Azure Cloud AI Agent",
    version="1.0.0",
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
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in .env to run the AI agent. Grafana and analytics work without it.",
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
        result = await Runner.run(agent, request.question)
        return AskResponse(answer=str(result.final_output), model=settings.openai_model)
