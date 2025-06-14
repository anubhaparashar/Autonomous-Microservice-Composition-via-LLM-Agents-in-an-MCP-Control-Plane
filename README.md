# MCP Control Plane

This repository contains the control plane implementation for the Autonomous Microservice Composition paper.

## Files

- `control_plane.py`: FastAPI app implementing:
  - Service registry (Redis)
  - LLM-based DAG planner (OpenAI GPT-4o-mini, PostgreSQL pgvector)
  - Execution orchestrator (HTTPX, NetworkX, retry/fallback logic)
  - REST endpoints: `/plan`, `/execute`, `/plan_and_execute`

## Setup

1. Configure environment variables:
   ```bash
   export REDIS_URL="redis://localhost:6379/0"
   export POSTGRES_DSN="host=localhost dbname=metadata user=postgres password=secret"
   export OPENAI_API_KEY="<your_openai_api_key>"
   ```
2. Install dependencies:
   ```bash
   pip install fastapi uvicorn redis httpx networkx psycopg2-binary pgvector openai
   ```
3. Run the app:
   ```bash
   uvicorn control_plane:app --reload --host 0.0.0.0 --port 8000
   ```

## Usage

- **Plan**: `POST /plan` with `{"intent": "<your intent>"}` to get a JSON DAG.
- **Execute**: `POST /execute` with `{"graph": <DAG>, "payload": {}}` to run the graph.
- **Plan and Execute**: `POST /plan_and_execute` with `{"intent": "<your intent>"}`.



## Features

- **Service Registry**  
  Stores microservice metadata (endpoint, input/output schemas, cost profiles, fallback options) in Redis.

- **Telemetry Integration**  
  Collects real-time metrics (latency, error rates, cost) via Prometheus → Redis, enabling adaptive planning.

- **LLM-Based DAG Planner**  
  Uses OpenAI GPT-4o-mini to translate user intents into JSON DAGs.  
  - Incorporates live telemetry and schema embeddings (pgvector in PostgreSQL).  
  - Supports per-node retry counts and ordered fallbacks.  
  - Generates human-readable explanations for auditability.

- **Execution Orchestrator**  
  Executes DAGs with NetworkX topological ordering, HTTPX calls, retries, and fallback logic.  
  - Records detailed execution traces.  
  - Exposes `/plan`, `/execute`, and `/plan_and_execute` REST endpoints.

## Prerequisites

- Python 3.11+
- Redis 6.x (or compatible)
- PostgreSQL 14.x with `pgvector` extension
- OpenAI API key

## Installation

1. **Clone the repository**  
   ```bash
   git clone https://github.com/your-org/mcp-control-plane.git
   cd mcp-control-plane

# MCP Control Plane

This repository implements an autonomous microservice control plane (MCP) that uses a telemetry-driven LLM planner to compose and orchestrate service workflows.

## Usage

### 1. Start Dependencies

Ensure the following are running and accessible:

- **Redis** (for service registry & telemetry storage)  
- **PostgreSQL** (with `pgvector` extension for schema embeddings)

### 2. Populate Service Registry & Telemetry

1. **Register each microservice** in Redis under key `mcp:service:<name>` with a JSON object, for example:
   ```json
   {
     "name": "user-profile",
     "endpoint": "http://user-profile-service/api",
     "input_schema": { /* JSON Schema */ },
     "output_schema": { /* JSON Schema */ },
     "cost_profile": 0.005,
     "fallback": "http://user-profile-fallback/api"
   }
