from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import LLMConfigUpdate
from app.application.llm_provider_service import LLMProviderError, LLMProviderService
from app.db.session import get_session
from app.infrastructure.llm.client import LLMNotConfigured

router = APIRouter(prefix="/settings", tags=["settings"])


def _error(exc: LLMProviderError) -> HTTPException:
    status = 400
    if exc.code == "NOT_FOUND":
        status = 404
    elif exc.code == "SECRET_ERROR":
        status = 409
    return HTTPException(status_code=status, detail=f"{exc.code}: {exc.message}")


@router.get("/llm")
async def llm_status(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        return await LLMProviderService(session).status()
    except LLMProviderError as exc:
        raise _error(exc) from exc


@router.put("/llm")
async def save_llm_config(
    payload: LLMConfigUpdate, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        return await LLMProviderService(session).save(
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
            clear_api_key=payload.clear_api_key,
        )
    except LLMProviderError as exc:
        raise _error(exc) from exc


@router.post("/llm/test")
async def test_llm_config(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        return await LLMProviderService(session).test()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=f"LLM_NOT_CONFIGURED: {exc}") from exc
    except LLMProviderError as exc:
        raise _error(exc) from exc
