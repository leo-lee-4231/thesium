from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import StreamCreate, StreamOut
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import Asset, Instrument, InvestmentStream, User
from app.db.session import get_session

router = APIRouter(prefix="/streams", tags=["streams"])


def _to_out(stream: InvestmentStream, asset: Asset, instrument: Instrument) -> StreamOut:
    return StreamOut(
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


@router.get("", response_model=list[StreamOut])
async def list_streams(session: AsyncSession = Depends(get_session)) -> list[StreamOut]:
    statement = (
        select(InvestmentStream, Asset, Instrument)
        .join(Asset, InvestmentStream.asset_id == Asset.id)
        .join(Instrument, InvestmentStream.primary_instrument_id == Instrument.id)
        .order_by(InvestmentStream.created_at.desc())
    )
    rows = await session.execute(statement)
    return [_to_out(stream, asset, instrument) for stream, asset, instrument in rows.all()]


@router.post("", response_model=StreamOut, status_code=201)
async def create_stream(
    payload: StreamCreate, session: AsyncSession = Depends(get_session)
) -> StreamOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be blank")
    if payload.market_type != "SPOT":
        raise HTTPException(
            status_code=422,
            detail="v1 primary instrument must be SPOT; SWAP is observation data",
        )
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=422, detail=f"unknown timezone: {payload.timezone}"
        ) from exc

    user = await session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
    if user is None:
        raise HTTPException(status_code=500, detail="LOCAL_USER_MISSING: run seed")

    active = await session.scalar(
        select(InvestmentStream).where(
            InvestmentStream.user_id == user.id,
            InvestmentStream.status == "ACTIVE",
        )
    )
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail="STREAM_LIMIT: v1 supports one ACTIVE investment product",
        )

    asset = await session.scalar(
        select(Asset).where(Asset.symbol == payload.asset_symbol.upper())
    )
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset not found: {payload.asset_symbol}")

    instrument = await session.scalar(
        select(Instrument).where(
            Instrument.asset_id == asset.id,
            Instrument.provider == payload.provider.lower(),
            Instrument.symbol == payload.instrument_symbol.upper(),
            Instrument.market_type == payload.market_type,
            Instrument.status == "ACTIVE",
        )
    )
    if instrument is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "instrument not found: "
                f"{payload.provider}/{payload.instrument_symbol}/{payload.market_type}"
            ),
        )

    stream = InvestmentStream(
        user_id=user.id,
        asset_id=asset.id,
        primary_instrument_id=instrument.id,
        name=name,
        status="ACTIVE",
        timezone=payload.timezone,
        monitor_interval_minutes=payload.monitor_interval_minutes,
        agent_enabled=payload.agent_enabled,
        config={},
    )
    session.add(stream)
    await session.commit()
    await session.refresh(stream)
    return _to_out(stream, asset, instrument)


@router.get("/{stream_id}", response_model=StreamOut)
async def get_stream(
    stream_id: UUID, session: AsyncSession = Depends(get_session)
) -> StreamOut:
    statement = (
        select(InvestmentStream, Asset, Instrument)
        .join(Asset, InvestmentStream.asset_id == Asset.id)
        .join(Instrument, InvestmentStream.primary_instrument_id == Instrument.id)
        .where(InvestmentStream.id == stream_id)
    )
    row = (await session.execute(statement)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="stream not found")
    stream, asset, instrument = row
    return _to_out(stream, asset, instrument)