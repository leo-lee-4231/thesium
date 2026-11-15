import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market import get_market_service
from app.api.v1.schemas import ChatMessageCreate, ConversationCreate
from app.application.conversation_service import ConversationError, ConversationService
from app.application.market_service import MarketService
from app.db.session import get_session

router = APIRouter(tags=["chat"])


def _error(exc: ConversationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=f"{exc.code}: {exc.message}")


def _sse(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.get("/streams/{stream_id}/conversations")
async def list_conversations(
    stream_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    try:
        return await ConversationService(session).conversations(stream_id, limit=limit)
    except ConversationError as exc:
        raise _error(exc) from exc


@router.post("/streams/{stream_id}/conversations", status_code=201)
async def create_conversation(
    stream_id: UUID,
    payload: ConversationCreate | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        conversation = await ConversationService(session).create(
            stream_id, title=payload.title if payload else None
        )
    except ConversationError as exc:
        raise _error(exc) from exc
    return {
        "id": conversation.id,
        "stream_id": conversation.stream_id,
        "title": conversation.title,
        "status": conversation.status,
        "summary": conversation.summary,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: UUID,
    after_seq: int | None = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    try:
        return await ConversationService(session).messages(
            conversation_id, after_seq=after_seq, limit=limit
        )
    except ConversationError as exc:
        raise _error(exc) from exc


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    payload: ChatMessageCreate,
    market: Annotated[MarketService, Depends(get_market_service)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        return await ConversationService(session, market).send(
            conversation_id,
            payload.content,
            client_message_id=payload.client_message_id or idempotency_key,
        )
    except ConversationError as exc:
        raise _error(exc) from exc


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    payload: ChatMessageCreate,
    market: Annotated[MarketService, Depends(get_market_service)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    service = ConversationService(session, market)

    async def events() -> AsyncIterator[str]:
        try:
            async for event in service.stream(
                conversation_id,
                payload.content,
                client_message_id=payload.client_message_id or idempotency_key,
            ):
                yield _sse(str(event["event"]), event["data"])  # type: ignore[arg-type]
        except ConversationError as exc:
            yield _sse(
                "error",
                {"code": exc.code, "message": exc.message, "status_code": exc.status_code},
            )
        except Exception as exc:  # noqa: BLE001 - keep SSE well-formed
            yield _sse(
                "error",
                {"code": "CHAT_STREAM_ERROR", "message": str(exc), "status_code": 502},
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
