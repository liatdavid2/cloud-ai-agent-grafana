# README

# Cloud AI Agent for Grafana

An AI-powered cloud analytics platform that combines Grafana dashboards, FastAPI analytics, MCP (Model Context Protocol), and Claude Desktop to analyze Azure virtual machine utilization using natural language.

The project demonstrates how an AI Agent can understand cloud infrastructure data, manipulate Grafana dashboards, create new visualizations, explain dashboards, and perform cloud capacity analysis without requiring users to know Grafana internals or API endpoints.

---
# Architecture

```text
                                     +----------------------+
                                     |   Claude Desktop     |
                                     | Natural Language     |
                                     +----------+-----------+
                                                |
                                           MCP Protocol
                                                |
                                                v
+----------------------------------------------------------------+
|                     MCP Server (FastMCP)                        |
|----------------------------------------------------------------|
| • Cloud analytics tools                                        |
| • Grafana dashboard tools                                      |
| • Create / Duplicate / Rename panels                           |
| • Change visualization                                         |
| • Explain dashboards                                            |
+--------------------------+-------------------------------------+
                           |
            +--------------+----------------+
            |                               |
            |                               |
            v                               v
+-------------------------+       +------------------------------+
| Analytics REST API      |       | Grafana HTTP API             |
| FastAPI                 |       | Dashboard Management         |
|-------------------------|       |------------------------------|
| /high-cpu               |       | Load Dashboard               |
| /underutilized          |       | Save Dashboard               |
| /rightsizing            |       | Update Panels                |
| /deployments            |       | Rename Panels                |
| /categories             |       | Change Visualization         |
| /anomalies              |       +--------------+---------------+
+-------------+-----------+                      |
              |                                  |
              |                                  |
              +-------------------+--------------+
                                  |
                                  v
                     +--------------------------+
                     |        Grafana           |
                     |--------------------------|
                     | Dashboards               |
                     | Tables                   |
                     | Bar Charts               |
                     | Pie Charts               |
                     | Time Series              |
                     +-------------+------------+
                                   |
                                   |
                                   v
                     Azure VM Usage Dataset
                     (Official Azure Dataset)
                             10,000 rows
```

---

# Features

## Cloud Analytics API

REST API built with FastAPI providing cloud utilization analytics.

Available analytics include:

* High CPU virtual machines
* Underutilized virtual machines
* Rightsizing candidates
* CPU anomaly detection
* Largest deployments
* VM category summaries
* Overall dataset statistics

---

## Grafana Dashboard

Interactive dashboard containing:

* Highest Average CPU
* Underutilized VMs
* Rightsizing Candidates
* Largest Deployments
* VM Categories
* CPU Distribution
* Dataset Overview

---

## MCP Server

The project exposes an MCP server that allows Claude Desktop to operate directly on Grafana.

Supported operations include:

* List dashboard panels
* Rename panels
* Change visualization
* Duplicate panels
* Create filtered versions of existing panels
* Explain dashboard panels

---

## Natural Language Dashboard Editing

Instead of manually editing Grafana, users can simply ask:

> Duplicate the Highest Average CPU panel and show only the top 10 VMs.

> Create a bar chart of long-running underutilized virtual machines.

> Rename this panel to "Capacity Risks".

> Change this visualization to a pie chart.

The AI Agent translates these requests into Grafana API operations automatically.

---

## Explain This Graph

Each dashboard panel includes an explanation endpoint.

Users can request:

> Explain this graph

The AI Agent summarizes:

* what the graph represents
* notable patterns
* potential operational impact
* cloud optimization recommendations

---

## Technologies

* Python
* FastAPI
* Grafana
* Docker
* MCP (FastMCP)
* Claude Desktop
* REST APIs
* Infinity Grafana Datasource

---

# Dataset

The project uses an official Microsoft Azure virtual machine usage dataset.

The repository automatically downloads the dataset if it does not already exist.

For development, a subset containing approximately 10,000 rows is used to keep startup fast while preserving realistic cloud utilization patterns.

---

# Architecture Components

```
Claude Desktop
        │
        ▼
MCP Server
        │
        ├──────────────► Grafana API
        │
        └──────────────► Analytics API
                                │
                                ▼
                      Azure VM Dataset
```

---

# Example Natural Language Commands

Create a new chart:

> Create a bar chart showing the top 10 deployments.

Duplicate an existing panel:

> Duplicate the Highest Average CPU panel and display only the top 10 results.

Cloud optimization:

> Show deployments with high core-hours but low average CPU.

Dashboard editing:

> Rename the Rightsizing panel to Capacity Optimization.

Visualization editing:

> Change the Largest Deployments table into a bar chart.

---

# Project Goals

The project demonstrates:

* AI-powered cloud operations
* MCP integration
* AI-controlled Grafana dashboards
* Natural language dashboard editing
* Cloud resource optimization
* Explainable dashboard analytics

---

# Future Improvements

* Automatic visualization recommendation
* AI-generated dashboards
* Multi-dashboard support
* Cost estimation
* Azure Advisor recommendations
* Cloud anomaly investigation
* Multi-cloud support (Azure, AWS, GCP)

