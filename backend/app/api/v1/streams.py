from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import StreamOut
from app.db.models import Asset, Instrument, InvestmentStream
from app.db.session import get_session

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("", response_model=list[StreamOut])
async def list_streams(session: AsyncSession = Depends(get_session)) -> list[StreamOut]:
    statement = (
        select(InvestmentStream, Asset, Instrument)
        .join(Asset, InvestmentStream.asset_id == Asset.id)
        .join(Instrument, InvestmentStream.primary_instrument_id == Instrument.id)
        .order_by(InvestmentStream.created_at.desc())
    )
    rows = await session.execute(statement)
    return [
        StreamOut(
            id=stream.id,
            name=stream.name,
            status=stream.status,
            timezone=stream.timezone,
            monitor_interval_minutes=stream.monitor_interval_minutes,
            agent_enabled=stream.agent_enabled,
            created_at=stream.created_at,
            asset_symbol=asset.symbol,
            asset_name=asset.name,
            provider=instrument.provider,
            instrument_symbol=instrument.symbol,
            market_type=instrument.market_type,
        )
        for stream, asset, instrument in rows.all()
    ]