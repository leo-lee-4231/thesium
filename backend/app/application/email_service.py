from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretError, decrypt_secret, encrypt_secret
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import EmailSettings, User
from app.infrastructure.email.sender import (
    EmailConfig,
    EmailError,
    OutboundEmail,
    send_email,
)

_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailSettingsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _validate(
    *,
    host: str,
    port: int,
    from_address: str,
) -> tuple[str, int, str]:
    host = host.strip()
    from_address = from_address.strip()
    if not host or "://" in host or any(char.isspace() for char in host):
        raise EmailSettingsError("VALIDATION", "SMTP host must be a hostname, not a URL")
    if not 1 <= port <= 65535:
        raise EmailSettingsError("VALIDATION", "SMTP port must be between 1 and 65535")
    if not _ADDRESS_RE.match(from_address):
        raise EmailSettingsError("VALIDATION", "from_address must be a valid email address")
    return host, port, from_address


class EmailSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise EmailSettingsError("NOT_FOUND", "local user not found; run seed")
        return user

    async def _row(self) -> EmailSettings | None:
        return await self._session.scalar(select(EmailSettings).limit(1))

    async def status(self) -> dict[str, object]:
        row = await self._row()
        if row is None:
            return {
                "configured": False,
                "host": "",
                "port": 587,
                "username": "",
                "from_address": "",
                "to_address": "",
                "from_name": "",
                "use_tls": True,
                "use_ssl": False,
                "has_password": False,
                "status": "UNTESTED",
                "last_tested_at": None,
                "verified_at": None,
            }
        return {
            "configured": bool(row.host and row.from_address),
            "host": row.host,
            "port": row.port,
            "username": row.username or "",
            "from_address": row.from_address,
            "to_address": row.to_address or "",
            "from_name": row.from_name or "",
            "use_tls": row.use_tls,
            "use_ssl": row.use_ssl,
            "has_password": bool(row.password_ciphertext),
            "status": row.status,
            "last_tested_at": row.last_tested_at,
            "verified_at": row.verified_at,
        }

    async def config(self) -> EmailConfig | None:
        row = await self._row()
        if row is None or not row.host or not row.from_address:
            return None
        password = None
        if row.password_ciphertext:
            try:
                password = decrypt_secret(row.password_ciphertext)
            except SecretError as exc:
                raise EmailSettingsError("SECRET_ERROR", str(exc)) from exc
        return EmailConfig(
            host=row.host,
            port=row.port,
            from_address=row.from_address,
            to_address=row.to_address,
            from_name=row.from_name,
            username=row.username,
            password=password,
            use_tls=row.use_tls,
            use_ssl=row.use_ssl,
        )

    async def save(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        to_address: str | None = None,
        from_name: str | None = None,
        username: str | None = None,
        password: str | None = None,
        clear_password: bool = False,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> dict[str, object]:
        host, port, from_address = _validate(
            host=host, port=port, from_address=from_address
        )
        if use_tls and use_ssl:
            raise EmailSettingsError(
                "VALIDATION", "use_tls and use_ssl are mutually exclusive"
            )
        username = (username or "").strip() or None
        from_name = (from_name or "").strip() or None
        if from_name and any(char in from_name for char in "\r\n"):
            raise EmailSettingsError("VALIDATION", "from_name must not contain newlines")
        to_address = (to_address or "").strip() or None
        if to_address is not None and not _ADDRESS_RE.match(to_address):
            raise EmailSettingsError("VALIDATION", "to_address must be a valid email address")
        if password is not None and password.strip() == "":
            password = None

        user = await self._user()
        row = await self._row()
        if row is None:
            row = EmailSettings(
                user_id=user.id,
                host=host,
                port=port,
                from_address=from_address,
                password_ciphertext=None,
            )
            self._session.add(row)

        row.host = host
        row.port = port
        row.from_address = from_address
        row.to_address = to_address
        row.from_name = from_name
        row.username = username
        row.use_tls = use_tls
        row.use_ssl = use_ssl
        if clear_password:
            row.password_ciphertext = None
        elif password is not None:
            row.password_ciphertext = encrypt_secret(password)
        row.status = "UNTESTED"
        row.last_tested_at = None
        row.verified_at = None
        await self._session.commit()
        return await self.status()

    async def _candidate_config(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        to_address: str | None,
        from_name: str | None,
        username: str | None,
        password: str | None,
        use_tls: bool,
        use_ssl: bool,
    ) -> EmailConfig:
        host, port, from_address = _validate(
            host=host, port=port, from_address=from_address
        )
        if use_tls and use_ssl:
            raise EmailSettingsError(
                "VALIDATION", "use_tls and use_ssl are mutually exclusive"
            )
        if password is not None and password.strip() == "":
            password = None
        if password is None:
            row = await self._row()
            if row is not None and row.password_ciphertext:
                try:
                    password = decrypt_secret(row.password_ciphertext)
                except SecretError as exc:
                    raise EmailSettingsError("SECRET_ERROR", str(exc)) from exc
        to_address = (to_address or "").strip() or None
        if to_address is not None and not _ADDRESS_RE.match(to_address):
            raise EmailSettingsError("VALIDATION", "to_address must be a valid email address")
        from_name = (from_name or "").strip() or None
        if from_name and any(char in from_name for char in "\r\n"):
            raise EmailSettingsError("VALIDATION", "from_name must not contain newlines")
        return EmailConfig(
            host=host,
            port=port,
            from_address=from_address,
            to_address=to_address,
            from_name=(from_name or "").strip() or None,
            username=(username or "").strip() or None,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
        )

    async def test_candidate(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        to_address: str | None = None,
        from_name: str | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        recipient: str | None = None,
    ) -> dict[str, object]:
        config = await self._candidate_config(
            host=host,
            port=port,
            from_address=from_address,
            to_address=to_address,
            from_name=from_name,
            username=username,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
        )
        return await self._send_test(config, to_address=recipient)

    async def test(self, *, recipient: str | None = None) -> dict[str, object]:
        config = await self.config()
        if config is None:
            raise EmailSettingsError("NOT_CONFIGURED", "SMTP is not configured")
        result = await self._send_test(config, to_address=recipient)
        row = await self._row()
        if row is not None:
            row.status = "OK" if result["ok"] else "FAILED"
            row.last_tested_at = datetime.now(UTC)
            if result["ok"]:
                row.verified_at = row.last_tested_at
            await self._session.commit()
        return result

    async def _send_test(
        self, config: EmailConfig, *, to_address: str | None = None
    ) -> dict[str, object]:
        recipient = (to_address or config.to_address or config.from_address).strip()
        if not _ADDRESS_RE.match(recipient):
            raise EmailSettingsError("VALIDATION", "test recipient is not a valid address")
        started = time.monotonic()
        try:
            await send_email(
                config,
                OutboundEmail(
                    to=recipient,
                    subject="[Thesium] SMTP 测试邮件",
                    text=(
                        "这是一封 Thesium 测试邮件。\n\n"
                        "收到它说明 SMTP 配置可用。通知只包含决策摘要，"
                        "不包含 API Key 或完整 Prompt。\n"
                    ),
                    html=(
                        "<p>这是一封 <strong>Thesium</strong> 测试邮件。</p>"
                        "<p>收到它说明 SMTP 配置可用。通知只包含决策摘要，"
                        "不包含 API Key 或完整 Prompt。</p>"
                    ),
                ),
            )
        except EmailError as exc:
            return {
                "ok": False,
                "error": exc.code,
                "message": exc.message,
                "latency_ms": int((time.monotonic() - started) * 1000),
            }
        return {
            "ok": True,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "to": recipient,
        }