from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm")
async def llm_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "configured": bool(settings.llm_base_url and settings.llm_model),
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "has_api_key": bool(settings.llm_api_key),
    }
