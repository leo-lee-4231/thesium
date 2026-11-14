from typing import Any

import pytest

from app.application.thesis_ai import ThesisAI
from app.domain.thesis import ThesisContent, build_diff


def test_text_only_is_minor() -> None:
    content = ThesisContent(thesis_statement="长期看涨")
    change_class, diff = build_diff(None, content)
    assert change_class == "MINOR"
    assert all(item["classification"] == "MINOR" for item in diff)


def test_first_material_outlook_is_material() -> None:
    content = ThesisContent.model_validate(
        {"market_outlook": {"short_term": "BEARISH", "long_term": "BULLISH"}}
    )
    change_class, _ = build_diff(None, content)
    assert change_class == "MATERIAL"


def test_outlook_change_is_material() -> None:
    previous = {"market_outlook": {"short_term": "NEUTRAL"}}
    content = ThesisContent.model_validate(
        {"market_outlook": {"short_term": "BEARISH"}}
    )
    change_class, diff = build_diff(previous, content)
    assert change_class == "MATERIAL"
    assert any(item["path"] == "/market_outlook/short_term" for item in diff)


def test_note_change_is_minor() -> None:
    previous = {"notes": "old"}
    content = ThesisContent(notes="new")
    change_class, diff = build_diff(previous, content)
    assert change_class == "MINOR"
    assert diff[0]["path"] == "/notes"


class FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        return self.payload


@pytest.mark.asyncio
async def test_polish_flags_number_change() -> None:
    ai = ThesisAI(
        FakeClient(
            {
                "polished_text": "回调到 65,000 附近",
                "change_notes": [],
                "warnings": [],
                "meaning_preserved": True,
            }
        )
    )
    result = await ai.polish("回调到 60,000 附近")
    assert result["warnings"]
    assert "数字" in result["warnings"][0]


@pytest.mark.asyncio
async def test_parse_validates_draft() -> None:
    ai = ThesisAI(
        FakeClient(
            {
                "draft": {"market_outlook": {"short_term": "BEARISH"}},
                "unparsed": [],
                "clarifying_questions": [],
                "warnings": [],
            }
        )
    )
    result = await ai.parse("短期看空")
    assert result["draft"]["market_outlook"]["short_term"] == "BEARISH"