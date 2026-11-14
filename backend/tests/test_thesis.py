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

@pytest.mark.asyncio
async def test_parse_normalizes_real_world_draft() -> None:
    ai = ThesisAI(
        FakeClient(
            {
                "draft": {
                    "market_outlook": {
                        "short_term": "bearish",
                        "medium_term": None,
                        "long_term": None,
                    },
                    "scenarios": [
                        {
                            "direction": "DOWN",
                            "target_price": 58000,
                            "description": "短期看空，支撑位 58000",
                        },
                        {
                            "direction": "up",
                            "target_price": "160000",
                            "description": "明年开多",
                        },
                    ],
                    "key_levels": {
                        "support": "58000",
                        "resistance": None,
                        "watch": "4w-3w之间；5w即止",
                    },
                },
                "unparsed": [],
                "clarifying_questions": [],
                "warnings": [],
            }
        )
    )
    result = await ai.parse("短期看空到 58000，明年看多到 16w")
    draft = result["draft"]
    assert draft["market_outlook"]["short_term"] == "BEARISH"
    assert draft["market_outlook"].get("long_term", "UNCERTAIN") == "UNCERTAIN"
    assert draft["scenarios"][0]["id"] == "S1"
    assert draft["scenarios"][1]["id"] == "S2"
    assert draft["scenarios"][0]["target_price"] == "58000"
    assert draft["scenarios"][0]["description"] == "短期看空，支撑位 58000"
    assert draft["key_levels"]["support"] == ["58000"]
    assert draft["key_levels"].get("resistance", []) == []
    assert draft["key_levels"]["watch"] == ["4w-3w之间；5w即止"]


@pytest.mark.asyncio
async def test_parse_limits_clarifying_questions() -> None:
    ai = ThesisAI(
        FakeClient(
            {
                "draft": {"thesis_statement": "test"},
                "unparsed": [],
                "clarifying_questions": [f"question {index}" for index in range(8)],
                "warnings": [],
            }
        )
    )
    result = await ai.parse("test")
    assert len(result["clarifying_questions"]) == 5
