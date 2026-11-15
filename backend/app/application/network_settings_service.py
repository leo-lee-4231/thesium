from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import NetworkSettings, User

DEFAULT_MARKET_PROXY_URL = "socks5h://127.0.0.1:7897"
_ALLOWED_SCHEMES = {"http", "https", "socks5", "socks5h"}


class NetworkSettingsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_proxy_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise NetworkSettingsError("VALIDATION", "proxy URL must not be empty")
    parsed = urlparse(value)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise NetworkSettingsError(
            "VALIDATION",
            "proxy URL must use http://, https://, socks5://, or socks5h://",
        )
    if not parsed.hostname:
        raise NetworkSettingsError("VALIDATION", "proxy URL must include a hostname")
    try:
        port = parsed.port
    except ValueError as exc:
        raise NetworkSettingsError("VALIDATION", "proxy URL has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise NetworkSettingsError("VALIDATION", "proxy port must be between 1 and 65535")
    return value


class NetworkSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise NetworkSettingsError("NOT_FOUND", "local user not found; run seed")
        return user

    async def _row(self) -> NetworkSettings | None:
        return await self._session.scalar(select(NetworkSettings).limit(1))

    async def status(self) -> dict[str, object]:
        env_proxy = (get_settings().market_proxy or "").strip() or None
        row = await self._row()
        if row is not None:
            enabled = row.market_proxy_enabled
            url = (row.market_proxy_url or "").strip() or env_proxy or DEFAULT_MARKET_PROXY_URL
            source = "database"
        elif env_proxy is not None:
            enabled = True
            url = env_proxy
            source = "environment"
        else:
            enabled = False
            url = DEFAULT_MARKET_PROXY_URL
            source = "none"
        return {
            "market_proxy_enabled": enabled,
            "market_proxy_url": url,
            "source": source,
            "effective_proxy": url if enabled else None,
            "env_fallback": env_proxy,
            "default_url": DEFAULT_MARKET_PROXY_URL,
        }

    async def effective_proxy(self) -> str | None:
        status = await self.status()
        value = status["effective_proxy"]
        return str(value) if value else None

    async def save(self, *, enabled: bool, url: str | None) -> dict[str, object]:
        value = (url or "").strip()
        if enabled and not value:
            value = DEFAULT_MARKET_PROXY_URL
        if value:
            value = validate_proxy_url(value)
        user = await self._user()
        row = await self._row()
        if row is None:
            row = NetworkSettings(user_id=user.id)
            self._session.add(row)
        row.market_proxy_enabled = enabled
        row.market_proxy_url = value or None
        await self._session.commit()
        return await self.status()