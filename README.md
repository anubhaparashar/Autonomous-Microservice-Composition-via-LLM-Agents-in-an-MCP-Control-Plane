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
