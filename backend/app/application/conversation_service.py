from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import ContextError, build_monitor_context, source_list
from app.agent.prompts import (
    CHAT_SUMMARY_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    chat_user_prompt,
)
from app.application.llm_provider_service import LLMProviderService
from app.application.market_service import MarketService
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import (
    AgentRun,
    Asset,
    Conversation,
    ConversationMessage,
    InvestmentStream,
    User,
)
from app.infrastructure.llm.client import LLMClient, LLMError, LLMNotConfigured

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "新对话"
READ_ONLY_GUARD = (
    "\n\n（只读提醒：我不会修改 Thesis、记录成交或下单；"
    "正式变更需要你在 Web 中确认。）"
)
_READ_ONLY_CLAIM = re.compile(
    r"(?:我(?:已|已经)|已(?:帮你|为你)|(?:帮你|为你))"
    r"(?:把[^，。；\n]{0,20})?(?:修改|更新|改成|改为|下单|买入|卖出|记录|添加|调整|执行|成交)"
)

_locks: dict[UUID, asyncio.Lock] = {}


class ConversationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def read_only_guard_triggered(text: str) -> bool:
    return bool(_READ_ONLY_CLAIM.search(text))


def _message_dict(message: ConversationMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "seq": message.seq,
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "agent_run_id": message.agent_run_id,
        "sources": message.sources,
        "created_at": message.created_at,
    }


class ConversationService:
    def __init__(self, session: AsyncSession, market: MarketService | None = None) -> None:
        self._session = session
        self._market = market

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise ConversationError("NOT_FOUND", "local user not found; run seed", 500)
        return user

    async def _stream(self, stream_id: UUID) -> InvestmentStream:
        stream = await self._session.get(InvestmentStream, stream_id)
        if stream is None:
            raise ConversationError("NOT_FOUND", "investment stream not found", 404)
        return stream

    async def create(self, stream_id: UUID, title: str | None = None) -> Conversation:
        stream = await self._stream(stream_id)
        asset = await self._session.get(Asset, stream.asset_id)
        user = await self._user()
        conversation = Conversation(
            user_id=user.id,
            stream_id=stream_id,
            title=(title or f"{asset.symbol if asset else '投资'} 对话").strip()
            or DEFAULT_TITLE,
        )
        self._session.add(conversation)
        await self._session.commit()
        await self._session.refresh(conversation)
        return conversation

    async def conversations(self, stream_id: UUID, limit: int = 20) -> list[dict[str, object]]:
        rows = (
            (
                await self._session.execute(
                    select(Conversation)
                    .where(Conversation.stream_id == stream_id)
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        result: list[dict[str, object]] = []
        for conversation in rows:
            count = (
                await self._session.scalar(
                    select(func.count(ConversationMessage.id)).where(
                        ConversationMessage.conversation_id == conversation.id
                    )
                )
                or 0
            )
            last = await self._session.scalar(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.seq.desc())
                .limit(1)
            )
            result.append(
                {
                    "id": conversation.id,
                    "stream_id": conversation.stream_id,
                    "title": conversation.title,
                    "status": conversation.status,
                    "summary": conversation.summary,
                    "message_count": int(count),
                    "last_message": (last.content[:120] if last is not None else None),
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                }
            )
        return result

    async def _conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationError("NOT_FOUND", "conversation not found", 404)
        return conversation

    async def messages(
        self, conversation_id: UUID, *, after_seq: int | None = None, limit: int = 200
    ) -> list[dict[str, object]]:
        await self._conversation(conversation_id)
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.seq.asc())
            .limit(limit)
        )
        if after_seq is not None:
            statement = statement.where(ConversationMessage.seq > after_seq)
        rows = (await self._session.execute(statement)).scalars().all()
        return [_message_dict(message) for message in rows]

    async def send(
        self,
        conversation_id: UUID,
        content: str,
        *,
        client_message_id: str | None = None,
    ) -> dict[str, object]:
        final: dict[str, object] | None = None
        async for event in self.stream(
            conversation_id, content, client_message_id=client_message_id
        ):
            if event["event"] == "error":
                data = event["data"]
                raise ConversationError(
                    str(data.get("code", "CHAT_ERROR")),
                    str(data.get("message", "chat failed")),
                    int(data.get("status_code", 502)),
                )
            if event["event"] == "done":
                final = event["data"]
        if final is None:
            raise ConversationError("CHAT_ERROR", "chat did not finish", 502)
        return final

    async def stream(
        self,
        conversation_id: UUID,
        content: str,
        *,
        client_message_id: str | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        content = content.strip()
        if not content:
            yield _event("error", {"code": "VALIDATION", "message": "消息不能为空"})
            return
        if len(content) > 8000:
            yield _event("error", {"code": "VALIDATION", "message": "消息过长（上限 8000 字）"})
            return

        lock = _locks.setdefault(conversation_id, asyncio.Lock())
        if lock.locked():
            yield _event(
                "error",
                {
                    "code": "CONVERSATION_BUSY",
                    "message": "上一轮回答还在生成，请稍候再发",
                    "status_code": 409,
                },
            )
            return
        async with lock:
            async for event in self._stream_locked(
                conversation_id, content, client_message_id=client_message_id
            ):
                yield event

    async def _stream_locked(
        self,
        conversation_id: UUID,
        content: str,
        *,
        client_message_id: str | None,
    ) -> AsyncIterator[dict[str, object]]:
        conversation = await self._conversation(conversation_id)
        existing = None
        if client_message_id:
            existing = await self._session.scalar(
                select(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.client_message_id == client_message_id,
                )
            )
        if existing is not None:
            assistant = await self._session.scalar(
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.seq > existing.seq,
                    ConversationMessage.role == "ASSISTANT",
                )
                .order_by(ConversationMessage.seq.asc())
                .limit(1)
            )
            if assistant is None:
                yield _event(
                    "error",
                    {
                        "code": "MESSAGE_IN_PROGRESS",
                        "message": "这条消息正在处理，请稍后刷新",
                        "status_code": 409,
                    },
                )
                return
            yield _event(
                "meta",
                {
                    "conversation_id": conversation.id,
                    "user_message_id": existing.id,
                    "assistant_message_id": assistant.id,
                    "agent_run_id": assistant.agent_run_id,
                    "replayed": True,
                },
            )
            yield _event("delta", {"text": assistant.content})
            yield _event(
                "done",
                {
                    "conversation_id": conversation.id,
                    "message_id": assistant.id,
                    "agent_run_id": assistant.agent_run_id,
                    "content": assistant.content,
                    "sources": assistant.sources,
                    "guard_triggered": False,
                    "replayed": True,
                },
            )
            return

        try:
            config = await LLMProviderService(self._session).config()
        except Exception as exc:  # noqa: BLE001 - surfaced as a chat error
            yield _event(
                "error",
                {
                    "code": "LLM_CONFIG_ERROR",
                    "message": f"LLM 配置不可用：{exc}",
                    "status_code": 503,
                },
            )
            return
        if config is None:
            yield _event(
                "error",
                {
                    "code": "LLM_NOT_CONFIGURED",
                    "message": "请先在 Settings 配置 LLM",
                    "status_code": 503,
                },
            )
            return

        conversation = await self._session.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .with_for_update()
        )
        if conversation is None:
            yield _event("error", {"code": "NOT_FOUND", "message": "conversation not found"})
            return
        max_seq = (
            await self._session.scalar(
                select(func.max(ConversationMessage.seq)).where(
                    ConversationMessage.conversation_id == conversation_id
                )
            )
            or 0
        )
        user_seq = int(max_seq) + 1
        user_message = ConversationMessage(
            conversation_id=conversation_id,
            seq=user_seq,
            role="USER",
            content=content,
            client_message_id=client_message_id,
        )
        self._session.add(user_message)
        if conversation.title in {DEFAULT_TITLE, ""}:
            conversation.title = content[:40]
        conversation.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(user_message)

        if self._market is None:
            yield _event(
                "error",
                {
                    "code": "MARKET_NOT_AVAILABLE",
                    "message": "行情服务未注入",
                    "status_code": 503,
                },
            )
            return

        yield _event(
            "status", {"message": "读取 Thesis、行情与持仓…", "stage": "context"}
        )
        try:
            ctx = await build_monitor_context(self._session, self._market, conversation.stream_id)
        except ContextError as exc:
            yield _event(
                "error",
                {
                    "code": exc.code,
                    "message": exc.message,
                    "status_code": 503 if exc.code == "MARKET_UNAVAILABLE" else 404,
                },
            )
            return
        sources = source_list(ctx)
        history_rows = (
            (
                await self._session.execute(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id == conversation_id,
                        ConversationMessage.seq < user_seq,
                        ConversationMessage.role.in_(["USER", "ASSISTANT"]),
                    )
                    .order_by(ConversationMessage.seq.desc())
                    .limit(12)
                )
            )
            .scalars()
            .all()
        )
        history = [
            {"role": message.role.lower(), "content": message.content}
            for message in reversed(history_rows)
        ]
        prompt = chat_user_prompt(
            context=ctx.context,
            summary=conversation.summary,
            messages=history,
            question=content,
            now=datetime.now(UTC).isoformat(),
            timezone=ctx.stream.timezone,
        )
        run_context = {
            **ctx.context,
            "conversation": {
                "id": str(conversation.id),
                "summary": conversation.summary,
                "history": history,
                "question": content,
            },
        }
        digest = hashlib.sha256(
            json.dumps(run_context, sort_keys=True, default=str, ensure_ascii=False).encode()
        ).hexdigest()
        provider_row = await LLMProviderService(self._session).current()
        run = AgentRun(
            stream_id=conversation.stream_id,
            task_type="CHAT",
            status="RUNNING",
            llm_provider_id=provider_row.id if provider_row else None,
            model=config.model,
            prompt_version="system.v1+chat.v1",
            thesis_version_id=ctx.thesis.id if ctx.thesis is not None else None,
            position_snapshot_id=ctx.position_snapshot.id if ctx.position_snapshot else None,
            derivative_snapshot_id=ctx.derivative_snapshot.id if ctx.derivative_snapshot else None,
            market_snapshot_id=ctx.market_snapshot.id if ctx.market_snapshot else None,
            conversation_id=conversation.id,
            input_digest=digest,
            input_context=run_context,
            tool_calls=sources,
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)

        yield _event(
            "meta",
            {
                "conversation_id": conversation.id,
                "user_message_id": user_message.id,
                "agent_run_id": run.id,
                "sources": sources,
                "replayed": False,
            },
        )
        yield _event("status", {"message": "生成回答…", "stage": "generating"})

        started = time.monotonic()
        parts: list[str] = []
        client = LLMClient(config)
        try:
            async for delta in client.chat_stream(CHAT_SYSTEM_PROMPT, prompt):
                parts.append(delta)
                yield _event("delta", {"text": delta})
        except asyncio.CancelledError:
            await self._cancel_run(run, "".join(parts), user_seq, conversation_id)
            raise
        except LLMNotConfigured as exc:
            await self._fail_run(run, "LLM_NOT_CONFIGURED", str(exc))
            yield _event(
                "error",
                {"code": "LLM_NOT_CONFIGURED", "message": str(exc), "status_code": 503},
            )
            return
        except LLMError as exc:
            await self._fail_run(run, exc.code, exc.message)
            yield _event(
                "error", {"code": exc.code, "message": exc.message, "status_code": 502}
            )
            return
        except Exception as exc:  # noqa: BLE001 - chat must never 500 the stream
            await self._fail_run(run, "CHAT_ERROR", str(exc))
            yield _event(
                "error",
                {"code": "CHAT_ERROR", "message": str(exc), "status_code": 502},
            )
            return

        answer = "".join(parts).strip()
        if not answer:
            await self._fail_run(run, "LLM_BAD_RESPONSE", "empty answer")
            yield _event(
                "error",
                {"code": "LLM_BAD_RESPONSE", "message": "模型返回空回答", "status_code": 502},
            )
            return
        guard = read_only_guard_triggered(answer)
        if guard:
            answer += READ_ONLY_GUARD
            yield _event("delta", {"text": READ_ONLY_GUARD})

        latency_ms = int((time.monotonic() - started) * 1000)
        assistant = ConversationMessage(
            conversation_id=conversation_id,
            seq=user_seq + 1,
            role="ASSISTANT",
            content=answer,
            status="COMPLETE",
            agent_run_id=run.id,
            sources=sources,
        )
        self._session.add(assistant)
        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)
        run.latency_ms = latency_ms
        run.output_raw = answer
        run.output_parsed = {"answer": answer, "guard_triggered": guard}
        conversation.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(assistant)

        try:
            await self._maybe_summarize(conversation, client, assistant.seq)
        except Exception:  # noqa: BLE001 - summary is best-effort
            logger.exception("conversation summary failed")
            with contextlib.suppress(Exception):
                await self._session.rollback()
        yield _event(
            "done",
            {
                "conversation_id": conversation.id,
                "message_id": assistant.id,
                "agent_run_id": run.id,
                "content": answer,
                "sources": sources,
                "guard_triggered": guard,
                "latency_ms": latency_ms,
                "replayed": False,
            },
        )

    async def _maybe_summarize(
        self, conversation: Conversation, client: LLMClient, through_seq: int
    ) -> None:
        if through_seq < 24 or through_seq - conversation.summarized_through_seq < 12:
            return
        rows = (
            (
                await self._session.execute(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id == conversation.id,
                        ConversationMessage.seq <= through_seq,
                    )
                    .order_by(ConversationMessage.seq.desc())
                    .limit(24)
                )
            )
            .scalars()
            .all()
        )
        transcript = "\n".join(
            f"{message.role}: {message.content}" for message in reversed(rows)
        )
        try:
            summary = await client.chat_text(
                CHAT_SUMMARY_SYSTEM_PROMPT, transcript, max_tokens=600
            )
        except LLMError as exc:
            logger.warning("conversation summary failed: %s", exc.code)
            summary = (conversation.summary or "")[-600:]
        conversation.summary = summary[:4000]
        conversation.summarized_through_seq = through_seq
        await self._session.commit()

    async def _fail_run(self, run: AgentRun, code: str, message: str) -> None:
        run.status = "FAILED"
        run.error_code = code
        run.error_message = message[:2000]
        run.finished_at = datetime.now(UTC)
        with contextlib.suppress(Exception):
            await self._session.commit()

    async def _cancel_run(
        self, run: AgentRun, partial: str, user_seq: int, conversation_id: UUID
    ) -> None:
        run.status = "FAILED"
        run.error_code = "CLIENT_DISCONNECTED"
        run.error_message = "client disconnected while streaming"
        run.finished_at = datetime.now(UTC)
        if partial.strip():
            self._session.add(
                ConversationMessage(
                    conversation_id=conversation_id,
                    seq=user_seq + 1,
                    role="ASSISTANT",
                    content=partial.strip(),
                    status="PARTIAL",
                    agent_run_id=run.id,
                )
            )
        with contextlib.suppress(Exception):
            await asyncio.shield(self._session.commit())


def _event(name: str, data: dict[str, object]) -> dict[str, object]:
    return {"event": name, "data": data}