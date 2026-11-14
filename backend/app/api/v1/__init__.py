from fastapi import APIRouter

from app.api.v1 import assets, market, meta, portfolio, streams

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(assets.router)
api_router.include_router(streams.router)
api_router.include_router(market.router)
api_router.include_router(portfolio.router)