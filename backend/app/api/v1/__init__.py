from fastapi import APIRouter

from app.api.v1 import assets, meta, streams

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(assets.router)
api_router.include_router(streams.router)