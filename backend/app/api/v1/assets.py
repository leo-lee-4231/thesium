from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import AssetOut, InstrumentOut
from app.db.models import Asset, Instrument
from app.db.session import get_session

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
async def list_assets(session: AsyncSession = Depends(get_session)) -> list[AssetOut]:
    assets = (await session.execute(select(Asset).order_by(Asset.symbol))).scalars().all()
    instruments = (await session.execute(select(Instrument))).scalars().all()

    by_asset: dict[str, list[InstrumentOut]] = defaultdict(list)
    for instrument in instruments:
        by_asset[str(instrument.asset_id)].append(InstrumentOut.model_validate(instrument))

    return [
        AssetOut(
            id=asset.id,
            symbol=asset.symbol,
            name=asset.name,
            kind=asset.kind,
            instruments=by_asset[str(asset.id)],
        )
        for asset in assets
    ]