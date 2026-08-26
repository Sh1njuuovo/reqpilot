"""FastAPI service around the ReqPilot pipeline."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from reqpilot.cli import _summary
from reqpilot.models import RequirementInput
from reqpilot.pipeline import PipelineResult, run_pipeline
from reqpilot.providers import ProviderError

app = FastAPI(title="ReqPilot API", version="0.1.0", description="Requirements engineering agent")

STORE: dict[str, PipelineResult] = {}


class RequirementRequest(RequirementInput):
    provider: Literal["llm"] = "llm"
    retriever_backend: str = "keyword"


def _get(run_id: str) -> PipelineResult:
    result = STORE.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return result


@app.post("/requirements", status_code=201)
def create_requirement(req: RequirementRequest) -> dict:
    try:
        result = run_pipeline(
            req.text,
            domain=req.domain,
            provider_name=req.provider,
            retriever_backend=req.retriever_backend,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    STORE[result.run.id] = result
    summary = _summary(result)
    summary["links"] = {
        "prd": f"/requirements/{result.run.id}/prd",
        "issues": f"/requirements/{result.run.id}/issues",
        "tasks": f"/requirements/{result.run.id}/tasks",
        "prototype": f"/requirements/{result.run.id}/prototype",
    }
    return summary


@app.get("/requirements/{run_id}")
def get_requirement(run_id: str) -> dict:
    return _summary(_get(run_id))


@app.get("/requirements/{run_id}/run")
def get_run(run_id: str) -> dict:
    return _get(run_id).run.model_dump()


@app.get("/requirements/{run_id}/prd")
def get_prd(run_id: str) -> dict:
    result = _get(run_id)
    if result.prd is None:
        raise HTTPException(status_code=404, detail="no PRD")
    return result.prd.model_dump()


@app.get("/requirements/{run_id}/prd.md", response_class=PlainTextResponse)
def get_prd_markdown(run_id: str) -> str:
    return _get(run_id).prd_markdown


@app.get("/requirements/{run_id}/issues")
def get_issues(run_id: str) -> list[dict]:
    return [i.model_dump() for i in _get(run_id).issues]


@app.get("/requirements/{run_id}/tasks")
def get_tasks(run_id: str) -> list[dict]:
    return [t.model_dump() for t in _get(run_id).tasks]


@app.get("/requirements/{run_id}/tasks.csv", response_class=PlainTextResponse)
def get_tasks_csv(run_id: str) -> str:
    return _get(run_id).tasks_csv


@app.get("/requirements/{run_id}/prototype", response_class=HTMLResponse)
def get_prototype(run_id: str) -> str:
    html = _get(run_id).prototype_html
    if not html:
        raise HTTPException(status_code=404, detail="no prototype")
    return html


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "runs": len(STORE)}
