from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    ThesisRejectRequest,
    ThesisTextRequest,
    ThesisVersionCreate,
)
from app.application.llm_provider_service import LLMProviderError, LLMProviderService
from app.application.thesis_ai import ThesisAI
from app.application.thesis_service import ThesisError, ThesisService
from app.db.models import InvestmentThesis
from app.db.session import get_session
from app.infrastructure.llm.client import LLMClient, LLMError, LLMNotConfigured

router = APIRouter(tags=["thesis"])


def _version(version: InvestmentThesis) -> dict[str, object]:
    return {
        "id": version.id,
        "stream_id": version.stream_id,
        "version": version.version,
        "status": version.status,
        "source": version.source,
        "change_class": version.change_class,
        "original_text": version.original_text,
        "final_text": version.final_text,
        "structured_content": version.structured_content,
        "diff_from_previous": version.diff_from_previous,
        "confirmed_at": version.confirmed_at,
        "effective_from": version.effective_from,
        "effective_until": version.effective_until,
        "created_at": version.created_at,
    }


def _error(exc: ThesisError) -> HTTPException:
    status = 400
    if exc.code == "NOT_FOUND":
        status = 404
    elif exc.code == "CONFLICT":
        status = 409
    elif exc.code == "VALIDATION":
        status = 422
    return HTTPException(status_code=status, detail=f"{exc.code}: {exc.message}")


async def _ai(session: AsyncSession) -> ThesisAI:
    config = await LLMProviderService(session).config()
    if config is None:
        raise LLMNotConfigured("LLM provider is not configured")
    return ThesisAI(LLMClient(config))


def _ai_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMProviderError):
        return HTTPException(status_code=409, detail=f"{exc.code}: {exc.message}")
    if isinstance(exc, LLMNotConfigured):
        return HTTPException(
            status_code=503,
            detail="LLM_NOT_CONFIGURED: set THESIUM_LLM_BASE_URL/MODEL/API_KEY",
        )
    return HTTPException(status_code=502, detail=f"LLM_ERROR: {exc}")


@router.get("/streams/{stream_id}/thesis")
async def get_active_thesis(
    stream_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object] | None:
    try:
        await ThesisService(session).ensure_stream(stream_id)
        version = await ThesisService(session).active(stream_id)
    except ThesisError as exc:
        raise _error(exc) from exc
    return _version(version) if version is not None else None


@router.get("/streams/{stream_id}/thesis/versions")
async def list_thesis_versions(
    stream_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    try:
        versions = await ThesisService(session).versions(stream_id, limit)
    except ThesisError as exc:
        raise _error(exc) from exc
    return [_version(version) for version in versions]


@router.get("/thesis/versions/{version_id}")
async def get_thesis_version(
    version_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        version = await ThesisService(session).get(version_id)
    except ThesisError as exc:
        raise _error(exc) from exc
    return _version(version)


@router.get("/thesis/versions/{version_id}/diff")
async def get_thesis_diff(
    version_id: UUID,
    against: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        result = await ThesisService(session).compare(version_id, against)
    except ThesisError as exc:
        raise _error(exc) from exc
    return {
        "version": _version(result["version"]),  # type: ignore[arg-type]
        "against": _version(result["against"]) if result["against"] else None,  # type: ignore[arg-type]
        "diff": result["diff"],
    }


@router.post("/streams/{stream_id}/thesis/versions", status_code=201)
async def create_thesis_version(
    stream_id: UUID,
    payload: ThesisVersionCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        version, requires_confirmation = await ThesisService(session).create(
            stream_id,
            original_text=payload.original_text,
            final_text=payload.final_text,
            structured_content=payload.structured_content,
            source=payload.source,
            source_agent_run_id=payload.source_agent_run_id,
            polish_agent_run_id=payload.polish_agent_run_id,
            base_version_id=payload.base_version_id,
        )
    except ThesisError as exc:
        raise _error(exc) from exc
    return {"version": _version(version), "requires_confirmation": requires_confirmation}


@router.post("/thesis/versions/{version_id}/confirm")
async def confirm_thesis_version(
    version_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        version = await ThesisService(session).confirm(version_id)
    except ThesisError as exc:
        raise _error(exc) from exc
    return _version(version)


@router.post("/thesis/versions/{version_id}/reject")
async def reject_thesis_version(
    version_id: UUID,
    payload: ThesisRejectRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        version = await ThesisService(session).reject(version_id, payload.reason)
    except ThesisError as exc:
        raise _error(exc) from exc
    return _version(version)


@router.post("/streams/{stream_id}/thesis/parse")
async def parse_thesis(
    stream_id: UUID,
    payload: ThesisTextRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        await ThesisService(session).ensure_stream(stream_id)
        result = await (await _ai(session)).parse(payload.text)
    except ThesisError as exc:
        raise _error(exc) from exc
    except (LLMProviderError, LLMNotConfigured, LLMError) as exc:
        raise _ai_error(exc) from exc
    return result


@router.post("/streams/{stream_id}/thesis/polish")
async def polish_thesis(
    stream_id: UUID,
    payload: ThesisTextRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        await ThesisService(session).ensure_stream(stream_id)
        result = await (await _ai(session)).polish(payload.text)
    except ThesisError as exc:
        raise _error(exc) from exc
    except (LLMProviderError, LLMNotConfigured, LLMError) as exc:
        raise _ai_error(exc) from exc
    return result
