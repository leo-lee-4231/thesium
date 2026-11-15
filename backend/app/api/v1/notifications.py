from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.notification_service import NotificationService
from app.db.session import get_session

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(
    stream_id: UUID | None = None,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    return await NotificationService(session).list_notifications(
        stream_id=stream_id, limit=limit
    )


@router.get("/streams/{stream_id}/notifications")
async def list_stream_notifications(
    stream_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    return await NotificationService(session).list_notifications(
        stream_id=stream_id, limit=limit
    )


@router.post("/notifications/{notification_id}/retry")
async def retry_notification(
    notification_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    notification = await NotificationService(session).retry(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="notification not found")
    return {
        "id": notification.id,
        "status": notification.status,
        "reason": notification.reason,
    }
