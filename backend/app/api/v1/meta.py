from fastapi import APIRouter

from app.api.v1.schemas import MetaOut
from app.core.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaOut)
async def get_meta() -> MetaOut:
    settings = get_settings()
    return MetaOut(
        name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        phase="P6",
        capabilities=[
            "health",
            "assets:list",
            "streams:list",
            "market:okx",
            "portfolio:spot",
            "portfolio:perp",
            "thesis:versions",
            "agent:analyze",
            "agent:decisions",
            "agent:scheduler",
            "notifications:email",
            "notifications:policy",
            "chat:read-only",
        ],
    )