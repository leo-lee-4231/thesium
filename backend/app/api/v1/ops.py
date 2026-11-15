from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ops_service import OpsService
from app.db.session import get_session

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/status")
async def ops_status(
    stream_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    return await OpsService(session).summary(stream_id=stream_id)
