from fastapi import APIRouter

from app.api.v1 import (
    agent,
    assets,
    chat,
    market,
    meta,
    notifications,
    ops,
    portfolio,
    risk,
    settings,
    streams,
    thesis,
)

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(assets.router)
api_router.include_router(streams.router)
api_router.include_router(market.router)
api_router.include_router(portfolio.router)
api_router.include_router(thesis.router)
api_router.include_router(settings.router)
api_router.include_router(risk.router)
api_router.include_router(agent.router)
api_router.include_router(chat.router)
api_router.include_router(notifications.router)
api_router.include_router(ops.router)