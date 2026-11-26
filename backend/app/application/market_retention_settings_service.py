from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.users import LOCAL_USER_EMAIL
from app.db.models import MarketRetentionSettings, User


@dataclass(frozen=True)
class RetentionPolicy:
    enabled: bool
    candle_1h_days: int
    candle_4h_days: int
    candle_1d_days: int
    snapshot_days: int


class RetentionSettingsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


DEFAULT_RETENTION_POLICY = RetentionPolicy(
    enabled=True,
    candle_1h_days=365,
    candle_4h_days=730,
    candle_1d_days=1825,
    snapshot_days=90,
)


def default_policy() -> RetentionPolicy:
    return DEFAULT_RETENTION_POLICY


def validate_policy(policy: RetentionPolicy) -> RetentionPolicy:
    if not 1 <= policy.candle_1h_days <= 3650:
        raise RetentionSettingsError("VALIDATION", "1h retention must be 1..3650 days")
    if not 1 <= policy.candle_4h_days <= 3650:
        raise RetentionSettingsError("VALIDATION", "4h retention must be 1..3650 days")
    if not 1 <= policy.candle_1d_days <= 7300:
        raise RetentionSettingsError("VALIDATION", "1d retention must be 1..7300 days")
    if not 1 <= policy.snapshot_days <= 3650:
        raise RetentionSettingsError("VALIDATION", "snapshot retention must be 1..3650 days")
    if not policy.candle_1h_days <= policy.candle_4h_days <= policy.candle_1d_days:
        raise RetentionSettingsError("VALIDATION", "retention must satisfy 1h <= 4h <= 1d")
    return policy


class MarketRetentionSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise RetentionSettingsError("NOT_FOUND", "local user not found; run seed")
        return user

    async def _row(self) -> MarketRetentionSettings | None:
        return await self._session.scalar(select(MarketRetentionSettings).limit(1))

    async def policy(self) -> RetentionPolicy:
        row = await self._row()
        if row is None:
            return default_policy()
        return validate_policy(
            RetentionPolicy(
                enabled=row.enabled,
                candle_1h_days=row.candle_1h_days,
                candle_4h_days=row.candle_4h_days,
                candle_1d_days=row.candle_1d_days,
                snapshot_days=row.snapshot_days,
            )
        )

    async def status(self) -> dict[str, object]:
        policy = await self.policy()
        row = await self._row()
        defaults = default_policy()
        return {
            "enabled": policy.enabled,
            "candle_1h_days": policy.candle_1h_days,
            "candle_4h_days": policy.candle_4h_days,
            "candle_1d_days": policy.candle_1d_days,
            "snapshot_days": policy.snapshot_days,
            "source": "database" if row is not None else "defaults",
            "defaults": {
                "enabled": defaults.enabled,
                "candle_1h_days": defaults.candle_1h_days,
                "candle_4h_days": defaults.candle_4h_days,
                "candle_1d_days": defaults.candle_1d_days,
                "snapshot_days": defaults.snapshot_days,
            },
            "updated_at": row.updated_at.isoformat() if row is not None else None,
        }

    async def save(
        self,
        *,
        enabled: bool,
        candle_1h_days: int,
        candle_4h_days: int,
        candle_1d_days: int,
        snapshot_days: int,
    ) -> dict[str, object]:
        policy = validate_policy(
            RetentionPolicy(
                enabled=enabled,
                candle_1h_days=candle_1h_days,
                candle_4h_days=candle_4h_days,
                candle_1d_days=candle_1d_days,
                snapshot_days=snapshot_days,
            )
        )
        user = await self._user()
        row = await self._row()
        if row is None:
            row = MarketRetentionSettings(user_id=user.id)
            self._session.add(row)
        row.enabled = policy.enabled
        row.candle_1h_days = policy.candle_1h_days
        row.candle_4h_days = policy.candle_4h_days
        row.candle_1d_days = policy.candle_1d_days
        row.snapshot_days = policy.snapshot_days
        await self._session.commit()
        return await self.status()
