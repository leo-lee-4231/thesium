from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import StreamOut
from app.db.models import InvestmentStream
from app.db.session import get_session

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("", response_model=list[StreamOut])
async def list_streams(session: AsyncSession = Depends(get_session)) -> list[InvestmentStream]:
    result = await session.execute(
        select(InvestmentStream).order_by(InvestmentStream.created_at.desc())
    )
    return list(result.scalars().all())