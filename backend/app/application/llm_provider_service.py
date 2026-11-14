from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretError, decrypt_secret, encrypt_secret
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import LLMProvider, User
from app.infrastructure.llm.client import LLMClient, LLMConfig, LLMError, LLMNotConfigured


class LLMProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LLMProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise LLMProviderError("NOT_FOUND", "local user not found; run seed")
        return user

    async def _row(self) -> LLMProvider | None:
        return await self._session.scalar(
            select(LLMProvider).order_by(LLMProvider.created_at.asc()).limit(1)
        )

    async def config(self) -> LLMConfig | None:
        row = await self._row()
        if row is not None and row.base_url and row.model:
            api_key = None
            if row.api_key_ciphertext:
                try:
                    api_key = decrypt_secret(row.api_key_ciphertext)
                except SecretError as exc:
                    raise LLMProviderError("SECRET_ERROR", str(exc)) from exc
            return LLMConfig(base_url=row.base_url.rstrip("/"), model=row.model, api_key=api_key)
        return LLMConfig.from_settings()

    async def status(self) -> dict[str, object]:
        row = await self._row()
        if row is not None and row.base_url and row.model:
            return {
                "configured": True,
                "source": "database",
                "base_url": row.base_url,
                "model": row.model,
                "has_api_key": bool(row.api_key_ciphertext),
                "api_key_hint": row.api_key_hint,
                "status": row.status,
                "last_tested_at": row.last_tested_at,
            }
        env_config = LLMConfig.from_settings()
        if env_config is not None:
            return {
                "configured": True,
                "source": "environment",
                "base_url": env_config.base_url,
                "model": env_config.model,
                "has_api_key": bool(env_config.api_key),
                "api_key_hint": None,
                "status": "ENV",
                "last_tested_at": None,
            }
        return {
            "configured": False,
            "source": "none",
            "base_url": "",
            "model": "",
            "has_api_key": False,
            "api_key_hint": None,
            "status": "UNTESTED",
            "last_tested_at": None,
        }

    async def save(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        clear_api_key: bool = False,
    ) -> dict[str, object]:
        base_url = base_url.strip().rstrip("/")
        model = model.strip()
        if not base_url.startswith(("http://", "https://")):
            raise LLMProviderError("VALIDATION", "base_url must start with http:// or https://")
        if not model:
            raise LLMProviderError("VALIDATION", "model must not be empty")
        if api_key is not None and api_key.strip() == "":
            api_key = None

        user = await self._user()
        row = await self._row()
        if row is None:
            row = LLMProvider(
                user_id=user.id,
                name="default",
                base_url=base_url,
                api_key_ciphertext=b"",
                model=model,
            )
            self._session.add(row)
        else:
            row.base_url = base_url
            row.model = model

        if clear_api_key:
            row.api_key_ciphertext = b""
            row.api_key_hint = None
        elif api_key is not None:
            row.api_key_ciphertext = encrypt_secret(api_key)
            row.api_key_hint = api_key[-4:]
        row.status = "UNTESTED"
        row.last_tested_at = None
        await self._session.commit()
        return await self.status()

    async def test(self) -> dict[str, object]:
        config = await self.config()
        if config is None:
            raise LLMNotConfigured("LLM provider is not configured")
        client = LLMClient(config)
        row = await self._row()
        try:
            result = await client.ping()
            if row is not None:
                row.status = "OK"
                row.last_tested_at = datetime.now(UTC)
                await self._session.commit()
            return result
        except LLMError as exc:
            if row is not None:
                row.status = "FAILED"
                row.last_tested_at = datetime.now(UTC)
                await self._session.commit()
            return {"ok": False, "error": exc.code, "message": exc.message}