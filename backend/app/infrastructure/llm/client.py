import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class LLMNotConfigured(Exception):
    pass


class LLMError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None = None

    @classmethod
    def from_settings(cls) -> "LLMConfig | None":
        settings = get_settings()
        base_url = (settings.llm_base_url or "").strip()
        model = (settings.llm_model or "").strip()
        if not base_url or not model:
            return None
        return cls(
            base_url=base_url.rstrip("/"),
            model=model,
            api_key=settings.llm_api_key or None,
        )


def _strip_fence(value: str) -> str:
    text = value.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1) if match else text


class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or LLMConfig.from_settings()

    @property
    def configured(self) -> bool:
        return self._config is not None

    @property
    def config(self) -> LLMConfig | None:
        return self._config

    def _headers(self) -> dict[str, str]:
        assert self._config is not None
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        assert self._config is not None
        url = f"{self._config.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), trust_env=True) as client:
            try:
                response = await client.post(url, headers=self._headers(), json=payload)
                if response.status_code == 400 and "response_format" in response.text:
                    payload.pop("response_format", None)
                    response = await client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                raise LLMError("LLM_TIMEOUT", "LLM request timed out") from exc
            except httpx.HTTPStatusError as exc:
                raise LLMError(
                    "LLM_UPSTREAM_ERROR",
                    f"LLM HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError("LLM_UPSTREAM_ERROR", str(exc)) from exc

    async def ping(self) -> dict[str, Any]:
        if not self.configured:
            raise LLMNotConfigured("LLM provider is not configured")
        started = time.monotonic()
        response = await self._post(
            {
                "model": self._config.model,  # type: ignore[union-attr]
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }
        )
        return {
            "ok": True,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "status_code": response.status_code,
        }

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            raise LLMNotConfigured(
                "LLM provider is not configured; set it in Settings"
            )
        payload = {
            "model": self._config.model,  # type: ignore[union-attr]
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        response = await self._post(payload)
        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM_BAD_RESPONSE", "LLM response missing content") from exc
        try:
            parsed = json.loads(_strip_fence(content))
        except json.JSONDecodeError as exc:
            raise LLMError("LLM_BAD_JSON", "LLM did not return valid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("LLM_BAD_JSON", "LLM JSON must be an object")
        return parsed
