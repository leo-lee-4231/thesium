from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market import get_market_service
from app.application.digest_service import DigestError, DigestService
from app.application.market_service import MarketService
from app.application.ops_service import OpsService
from app.db.models import DailyDigest, InvestmentStream
from app.db.session import get_session

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/status")
async def ops_status(
    stream_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    return await OpsService(session).summary(stream_id=stream_id)


@router.post("/digest/run")
async def run_daily_digest(
    market: Annotated[MarketService, Depends(get_market_service)],
    stream_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    stream = (
        await session.get(InvestmentStream, stream_id)
        if stream_id is not None
        else await session.scalar(
            select(InvestmentStream)
            .where(InvestmentStream.status == "ACTIVE")
            .order_by(InvestmentStream.created_at.desc())
            .limit(1)
        )
    )
    if stream is None:
        raise HTTPException(status_code=404, detail="investment stream not found")
    try:
        zone = ZoneInfo(stream.timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    local_date = datetime.now(UTC).astimezone(zone).date()
    existing = await session.scalar(
        select(DailyDigest).where(
            DailyDigest.stream_id == stream.id,
            DailyDigest.local_date == local_date,
        )
    )
    already_sent = existing is not None and existing.status == "SENT"
    try:
        digest = await DigestService(session, market).ensure_and_send(
            stream_id=stream.id, local_date=local_date
        )
    except DigestError as exc:
        raise HTTPException(status_code=503, detail=f"DIGEST_FAILED: {exc}") from exc
    return {
        "id": digest.id,
        "local_date": digest.local_date,
        "status": digest.status,
        "subject": digest.subject,
        "sent_at": digest.sent_at,
        "error": digest.error,
        "already_sent": already_sent,
    }
