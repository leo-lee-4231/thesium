import json
import re
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


def _strip_fence(value: str) -> str:
    text = value.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1) if match else text


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = (settings.llm_base_url or "").rstrip("/")
        self._api_key = settings.llm_api_key
        self._model = settings.llm_model

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._model)

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            raise LLMNotConfigured(
                "LLM provider is not configured; set THESIUM_LLM_BASE_URL/MODEL/API_KEY"
            )
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), trust_env=True) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 400 and "response_format" in response.text:
                    payload.pop("response_format", None)
                    response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise LLMError("LLM_TIMEOUT", "LLM request timed out") from exc
            except httpx.HTTPStatusError as exc:
                raise LLMError(
                    "LLM_UPSTREAM_ERROR",
                    f"LLM HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError("LLM_UPSTREAM_ERROR", str(exc)) from exc

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
