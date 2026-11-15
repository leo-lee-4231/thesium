from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import AgentError, AgentRuntime
from app.api.v1.market import get_market_service
from app.application.market_service import MarketService
from app.db.models import AgentRun, InvestmentDecision
from app.db.session import get_session

router = APIRouter(tags=["agent"])


def _run(run: AgentRun) -> dict[str, object]:
    return {
        "id": run.id,
        "stream_id": run.stream_id,
        "task_type": run.task_type,
        "status": run.status,
        "model": run.model,
        "prompt_version": run.prompt_version,
        "thesis_version_id": run.thesis_version_id,
        "position_snapshot_id": run.position_snapshot_id,
        "derivative_snapshot_id": run.derivative_snapshot_id,
        "market_snapshot_id": run.market_snapshot_id,
        "input_digest": run.input_digest,
        "input_context": run.input_context,
        "tool_calls": run.tool_calls,
        "output_parsed": run.output_parsed,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def _decision(decision: InvestmentDecision) -> dict[str, object]:
    return {
        "id": decision.id,
        "stream_id": decision.stream_id,
        "agent_run_id": decision.agent_run_id,
        "schema_version": decision.schema_version,
        "decision": decision.decision,
        "confidence": str(decision.confidence),
        "priority": decision.priority,
        "summary": decision.summary,
        "evidence_for": decision.evidence_for,
        "evidence_against": decision.evidence_against,
        "thesis_alignment": decision.thesis_alignment,
        "position_impact": decision.position_impact,
        "derivative_recommendation": decision.derivative_recommendation,
        "changes_since_previous": decision.changes_since_previous,
        "invalidation_conditions": decision.invalidation_conditions,
        "data_quality": decision.data_quality,
        "notification_recommendation": decision.notification_recommendation,
        "created_at": decision.created_at,
    }


def _error(exc: AgentError) -> HTTPException:
    status = 500
    if exc.code == "NOT_FOUND":
        status = 404
    elif exc.code in {"LLM_NOT_CONFIGURED", "MARKET_UNAVAILABLE"}:
        status = 503
    elif exc.code in {"SCHEMA_INVALID", "LLM_UPSTREAM_ERROR", "LLM_TIMEOUT"}:
        status = 502
    detail = f"{exc.code}: {exc.message}"
    if exc.run_id:
        detail += f" (run {exc.run_id})"
    return HTTPException(status_code=status, detail=detail)


@router.post("/streams/{stream_id}/analyze")
async def analyze(
    stream_id: UUID,
    market: Annotated[MarketService, Depends(get_market_service)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    runtime = AgentRuntime(session, market)
    try:
        result = await runtime.run_monitor(stream_id)
    except AgentError as exc:
        raise _error(exc) from exc
    return {"run": _run(result["run"]), "decision": _decision(result["decision"])}


@router.get("/streams/{stream_id}/decisions")
async def list_decisions(
    stream_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(InvestmentDecision)
        .where(InvestmentDecision.stream_id == stream_id)
        .order_by(InvestmentDecision.created_at.desc())
        .limit(limit)
    )
    return [_decision(item) for item in rows.scalars().all()]


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    decision = await session.get(InvestmentDecision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return _decision(decision)


@router.get("/agent-runs/{run_id}")
async def get_run(
    run_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return _run(run)


@router.get("/streams/{stream_id}/agent-runs")
async def list_runs(
    stream_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(AgentRun)
        .where(AgentRun.stream_id == stream_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    return [_run(item) for item in rows.scalars().all()]
