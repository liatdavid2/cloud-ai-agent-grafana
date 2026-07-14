# Azure Cloud AI Agent with MCP and Grafana

A portfolio project that analyzes a **real, anonymized Microsoft Azure VM workload trace** using:

- a local CSV subset of 10,000 VM records
- FastAPI analytics endpoints
- Grafana with the Infinity REST/JSON data source
- an MCP server exposing cloud-analysis tools
- an optional OpenAI Agent that calls the MCP tools

There is **no PostgreSQL and no Prometheus**. The CSV is loaded into memory by FastAPI and the MCP server.

## Architecture

```text
Official Azure VM trace (.csv.gz)
            |
     download_data.py
            |
  data/azure_vm_usage_10000.csv
        /          \
       v            v
 FastAPI JSON     MCP Server <---- OpenAI Agent API
       |
       v
 Grafana Infinity datasource
```

## Dataset

The download script streams the official Azure Public Dataset V1 VM table and stops after 10,000 valid rows. It does not need to save or unpack the full trace.

Included fields:

- anonymized VM, subscription, and deployment identifiers
- VM creation and deletion times
- average, maximum, and P95 CPU utilization
- VM category
- allocated cores and memory

The dataset does not provide application logs, Azure region names, customer identities, or real prices. The agent instructions explicitly prohibit inventing these details.

## Start with Docker

1. Extract the ZIP and open a terminal in the project directory.
2. Create the environment file:

Windows Command Prompt:

```bat
copy .env.example .env
```

PowerShell, macOS, or Linux:

```bash
cp .env.example .env
```

3. Add an OpenAI API key to `.env` only when you want to use the AI Agent:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini
```

4. Start everything:

```bash
docker compose up --build
```

On the first run, `data-init` downloads and creates:

```text
data/azure_vm_usage_10000.csv
```

On later runs, the script detects that the file exists and skips the download.

## Services

| Service | URL |
|---|---|
| Grafana | http://localhost:3000 |
| FastAPI documentation | http://localhost:8000/docs |
| MCP Streamable HTTP endpoint | http://localhost:8002/mcp |
| AI Agent API documentation | http://localhost:8003/docs |

Grafana credentials:

```text
username: admin
password: admin
```

The dashboard is provisioned automatically under the **Azure Cloud AI** folder.

## Run only the dataset script

With Python installed locally:

```bash
pip install requests
python scripts/download_data.py --rows 10000
```

Choose a different subset size:

```bash
python scripts/download_data.py --rows 25000
```

Force a new download:

```bash
python scripts/download_data.py --rows 10000 --force
```

## Ask the AI Agent

The agent works only when `OPENAI_API_KEY` is configured. Grafana, FastAPI, and MCP do not require the key.

```bash
curl -X POST http://localhost:8003/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Which VMs should be prioritized for rightsizing, and why?"}'
```

Windows Command Prompt:

```bat
curl -X POST http://localhost:8003/ask -H "Content-Type: application/json" -d "{\"question\":\"Investigate the most important cloud capacity risks.\"}"
```

Suggested questions:

- Which VMs have sustained high CPU?
- Which long-running VMs appear overprovisioned?
- Compare utilization between VM categories.
- What are the largest deployments by core-hours?
- Investigate CPU anomalies and separate evidence from hypotheses.

## MCP tools

- `get_cloud_overview`
- `find_overloaded_vms`
- `find_underutilized_vms`
- `recommend_rightsizing`
- `detect_cpu_anomalies`
- `summarize_vm_categories`
- `get_largest_deployments`

## Direct API examples

```bash
curl http://localhost:8000/summary
curl "http://localhost:8000/high-cpu?threshold=80&limit=10"
curl "http://localhost:8000/underutilized?threshold=10&limit=10"
curl "http://localhost:8000/rightsizing?limit=10"
curl "http://localhost:8000/anomalies?z_threshold=3&limit=10"
```

## Run tests

```bash
pytest -q
```

## Notes

- The project uses rules and a z-score for transparent baseline analysis. A later version can add Isolation Forest or forecasting.
- Rightsizing recommendations are intentionally conservative and do not claim monetary savings because real Azure pricing is not part of the trace.
- The Grafana Infinity plugin reads the FastAPI JSON endpoints directly, so no database is needed.
