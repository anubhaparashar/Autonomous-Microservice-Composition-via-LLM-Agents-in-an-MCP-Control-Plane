# control_plane.py

import os
import json
import redis
import httpx
import networkx as nx
import logging
import psycopg2
from pgvector.psycopg2 import register_vector
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai

# ─── Configuration ─────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "host=localhost dbname=metadata user=postgres password=secret")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVICES_PREFIX = "mcp:service:"     # Redis key prefix for service entries

openai.api_key = OPENAI_API_KEY

# ─── Service Registry ─────────────────────────────────────────────────────────

class ServiceRegistry:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    def list_services(self):
        \"\"\"Returns list of {name, endpoint, input_schema, output_schema, cost_profile, fallback}\"\"\"
        services = []
        for key in self.redis.scan_iter(f"{SERVICES_PREFIX}*"):
            services.append(json.loads(self.redis.get(key)))
        return services

# ─── Planner (LLM) ─────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    intent: str

class PlanResponse(BaseModel):
    graph: dict  # adjacency list + node metadata

class GraphPlanner:
    def __init__(self, registry: ServiceRegistry, pg_dsn: str):
        self.registry = registry
        self.conn = psycopg2.connect(pg_dsn)
        register_vector(self.conn)  # enable pgvector

    def _fetch_embeddings_metadata(self):
        \"\"\"Example: pull service schema embeddings from Postgres pgvector.\"\"\"
        with self.conn.cursor() as cur:
            cur.execute("SELECT name, input_schema_vector FROM service_schemas;")
            return cur.fetchall()

    def plan(self, intent: str) -> PlanResponse:
        services = self.registry.list_services()
        # build prompt
        prompt = (
            "You are an orchestration agent.  Given the user intent and available services,\\n"
            "output a JSON DAG specifying for each step: service_name, input_keys, next_steps, fallback.\\n\\n"
            "Available services:\\n"
        )
        for s in services:
            prompt += f"- {s['name']} (endpoint: {s['endpoint']}, inputs: {s['input_schema']}, outputs: {s['output_schema']})\\n"
        prompt += f"\\nUser intent: “{intent}”\\n\\nJSON DAG:"

        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":prompt}],
            temperature=0.2
        )
        dag = json.loads(resp.choices[0].message.content)
        return PlanResponse(graph=dag)

# ─── Orchestrator ──────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    graph: dict   # same format as PlanResponse.graph
    payload: dict

class ExecuteResponse(BaseModel):
    results: dict
    errors: dict

class Orchestrator:
    def __init__(self):
        self.client = httpx.AsyncClient()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("orchestrator")

    async def execute(self, graph: dict, payload: dict) -> ExecuteResponse:
        G = nx.DiGraph()
        # build networkx graph nodes
        for node in graph["nodes"]:
            G.add_node(node["name"], **node)
        # add edges
        for edge in graph["edges"]:
            G.add_edge(edge["from"], edge["to"], fallback=edge.get("fallback"))

        results, errors = {}, {}
        # simple topological execution
        for name in nx.topological_sort(G):
            node = G.nodes[name]
            service_url = node["endpoint"]
            inputs = {k: results.get(v, payload.get(v)) for k, v in node["inputs"].items()}
            try:
                resp = await self.client.post(service_url, json=inputs, timeout=5.0)
                resp.raise_for_status()
                results[name] = resp.json()
            except Exception as e:
                self.logger.error(f"Service {name} failed: {e}")
                errors[name] = str(e)
                # try fallback if defined
                in_edges = list(G.in_edges(name))
                fallback = None
                if in_edges:
                    fallback = G.edges[in_edges[0]][name].get("fallback")
                if fallback:
                    self.logger.info(f"Attempting fallback {fallback} for {name}")
                    try:
                        resp = await self.client.post(fallback, json=inputs, timeout=5.0)
                        resp.raise_for_status()
                        results[name] = resp.json()
                    except Exception as e2:
                        self.logger.error(f"Fallback {fallback} failed: {e2}")
                        errors[name] += f"; fallback failed: {e2}"
                else:
                    raise HTTPException(status_code=502, detail=f"{name} failed and no fallback available")
        return ExecuteResponse(results=results, errors=errors)

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI()
registry = ServiceRegistry(REDIS_URL)
planner = GraphPlanner(registry, POSTGRES_DSN)
orch = Orchestrator()

@app.post("/plan", response_model=PlanResponse)
def plan_intent(req: PlanRequest):
    return planner.plan(req.intent)

@app.post("/execute", response_model=ExecuteResponse)
async def run_graph(req: ExecuteRequest):
    return await orch.execute(req.graph, req.payload)

@app.post("/plan_and_execute", response_model=ExecuteResponse)
async def plan_and_run(req: PlanRequest):
    plan = planner.plan(req.intent)
    return await orch.execute(plan.graph, {})

# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("control_plane:app", host="0.0.0.0", port=8000, reload=True)
