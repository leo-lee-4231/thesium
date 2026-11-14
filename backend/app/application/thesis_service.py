from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InvestmentStream, InvestmentThesis
from app.domain.thesis import (
    ThesisValidationError,
    build_diff,
    content_from_dict,
    normalized_content,
)


class ThesisError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ThesisService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _stream(self, stream_id: UUID) -> InvestmentStream:
        stream = await self._session.get(InvestmentStream, stream_id)
        if stream is None:
            raise ThesisError("NOT_FOUND", "investment stream not found")
        return stream

    async def ensure_stream(self, stream_id: UUID) -> None:
        await self._stream(stream_id)

    async def active(self, stream_id: UUID) -> InvestmentThesis | None:
        return await self._session.scalar(
            select(InvestmentThesis).where(
                InvestmentThesis.stream_id == stream_id,
                InvestmentThesis.status == "ACTIVE",
            )
        )

    async def versions(self, stream_id: UUID, limit: int = 50) -> list[InvestmentThesis]:
        rows = await self._session.execute(
            select(InvestmentThesis)
            .where(InvestmentThesis.stream_id == stream_id)
            .order_by(InvestmentThesis.version.desc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def get(self, version_id: UUID) -> InvestmentThesis:
        version = await self._session.get(InvestmentThesis, version_id)
        if version is None:
            raise ThesisError("NOT_FOUND", "thesis version not found")
        return version

    async def create(
        self,
        stream_id: UUID,
        *,
        original_text: str,
        final_text: str | None,
        structured_content: dict,
        source: str = "USER",
        source_agent_run_id: UUID | None = None,
        polish_agent_run_id: UUID | None = None,
        base_version_id: UUID | None = None,
    ) -> tuple[InvestmentThesis, bool]:
        await self._stream(stream_id)
        if not original_text.strip():
            raise ThesisError("VALIDATION", "original_text must not be empty")
        try:
            content = content_from_dict(structured_content)
        except ThesisValidationError as exc:
            raise ThesisError("VALIDATION", exc.message) from exc

        active = await self.active(stream_id)
        if base_version_id is not None and (active is None or active.id != base_version_id):
            raise ThesisError("CONFLICT", "base thesis version is stale")

        previous = active.structured_content if active is not None else None
        change_class, diff = build_diff(previous, content)

        max_version = await self._session.scalar(
            select(func.max(InvestmentThesis.version)).where(
                InvestmentThesis.stream_id == stream_id
            )
        )
        now = datetime.now(UTC)

        # The partial unique indexes allow only one ACTIVE and one PENDING row
        # per stream, so retire the previous row before inserting the new one.
        if change_class == "MATERIAL":
            pending = await self._session.scalar(
                select(InvestmentThesis).where(
                    InvestmentThesis.stream_id == stream_id,
                    InvestmentThesis.status == "PENDING_CONFIRMATION",
                )
            )
            if pending is not None:
                pending.status = "REJECTED"
                await self._session.flush()
        elif active is not None:
            active.status = "SUPERSEDED"
            active.effective_until = now
            await self._session.flush()

        version = InvestmentThesis(
            stream_id=stream_id,
            version=(max_version or 0) + 1,
            status="PENDING_CONFIRMATION" if change_class == "MATERIAL" else "ACTIVE",
            source=source,
            change_class=change_class,
            original_text=original_text,
            final_text=final_text or original_text,
            structured_content=normalized_content(content),
            diff_from_previous=diff,
            source_agent_run_id=source_agent_run_id,
            polish_agent_run_id=polish_agent_run_id,
            confirmed_at=None if change_class == "MATERIAL" else now,
            effective_from=now,
        )
        self._session.add(version)
        await self._session.commit()
        await self._session.refresh(version)
        return version, change_class == "MATERIAL"

    async def confirm(self, version_id: UUID) -> InvestmentThesis:
        version = await self.get(version_id)
        if version.status != "PENDING_CONFIRMATION":
            raise ThesisError("CONFLICT", "only PENDING_CONFIRMATION can be confirmed")
        active = await self.active(version.stream_id)
        now = datetime.now(UTC)
        if active is not None and active.id != version.id:
            active.status = "SUPERSEDED"
            active.effective_until = now
            await self._session.flush()
        version.status = "ACTIVE"
        version.confirmed_at = now
        version.effective_from = now
        version.effective_until = None
        await self._session.commit()
        await self._session.refresh(version)
        return version

    async def reject(self, version_id: UUID, reason: str | None = None) -> InvestmentThesis:
        version = await self.get(version_id)
        if version.status != "PENDING_CONFIRMATION":
            raise ThesisError("CONFLICT", "only PENDING_CONFIRMATION can be rejected")
        version.status = "REJECTED"
        if reason:
            version.diff_from_previous = version.diff_from_previous or []
        await self._session.commit()
        await self._session.refresh(version)
        return version

    async def compare(
        self, version_id: UUID, against_id: UUID | None = None
    ) -> dict[str, object]:
        version = await self.get(version_id)
        if against_id is None:
            rows = await self.versions(version.stream_id, limit=1000)
            previous = next((item for item in rows if item.version < version.version), None)
        else:
            previous = await self.get(against_id)
        before = previous.structured_content if previous is not None else None
        content = content_from_dict(version.structured_content)
        _, diff = build_diff(before, content)
        return {
            "version": version,
            "against": previous,
            "diff": diff,
        }