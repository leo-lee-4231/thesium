from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Outlook = Literal["BULLISH", "NEUTRAL", "BEARISH", "UNCERTAIN"]
Horizon = Literal["DAYS", "WEEKS", "MONTHS", "YEARS"]
ScenarioDirection = Literal["UP", "DOWN", "RANGE"]
ScenarioHorizon = Literal["SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"]
ScenarioStatus = Literal["USER_EXPECTATION", "CONDITIONAL"]

MATERIAL_FIELDS = {
    "market_outlook",
    "time_horizon",
    "scenarios",
    "risk",
    "position_intent",
    "derivative_intent",
    "constraints",
}


class TimeHorizon(BaseModel):
    model_config = ConfigDict(extra="forbid")
    short_term: Horizon | None = None
    medium_term: Horizon | None = None
    long_term: Horizon | None = None


class MarketOutlook(BaseModel):
    model_config = ConfigDict(extra="forbid")
    short_term: Outlook = "UNCERTAIN"
    medium_term: Outlook = "UNCERTAIN"
    long_term: Outlook = "UNCERTAIN"


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    direction: ScenarioDirection
    target_price: str | None = None
    target_currency: str = "USDT"
    time_horizon: ScenarioHorizon = "SHORT_TERM"
    status: ScenarioStatus = "USER_EXPECTATION"
    conditions: list[str] = Field(default_factory=list)
    invalidation: str | None = None


class KeyLevels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    support: list[str] = Field(default_factory=list)
    resistance: list[str] = Field(default_factory=list)
    watch: list[str] = Field(default_factory=list)


class RiskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_drawdown_pct: str | None = None
    max_position_pct: str | None = None
    risk_budget_usd: str | None = None
    stop_loss_price: str | None = None
    take_profit_price: str | None = None


class PositionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_position_pct: str | None = None
    allow_add: bool | None = None
    allow_reduce: bool | None = None
    avoid_full_exit: bool | None = None


class DerivativeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_perpetual: bool | None = None
    allow_short: bool | None = None
    max_leverage: str | None = None
    max_margin_usd: str | None = None
    min_liquidation_buffer_pct: str | None = None


class ThesisContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1.0"
    thesis_statement: str | None = None
    purpose: str | None = None
    time_horizon: TimeHorizon = Field(default_factory=TimeHorizon)
    market_outlook: MarketOutlook = Field(default_factory=MarketOutlook)
    scenarios: list[Scenario] = Field(default_factory=list)
    key_levels: KeyLevels = Field(default_factory=KeyLevels)
    risk: RiskProfile = Field(default_factory=RiskProfile)
    position_intent: PositionIntent = Field(default_factory=PositionIntent)
    derivative_intent: DerivativeIntent = Field(default_factory=DerivativeIntent)
    constraints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    notes: str | None = None


class ThesisValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def content_from_dict(value: dict[str, Any] | None) -> ThesisContent:
    if not value:
        return ThesisContent()
    try:
        return ThesisContent.model_validate(value)
    except Exception as exc:
        raise ThesisValidationError(f"invalid structured_content: {exc}") from exc


def normalized_content(content: ThesisContent) -> dict[str, Any]:
    return content.model_dump(exclude_none=True, exclude_defaults=True)


def _is_meaningful_material(content: dict[str, Any]) -> bool:
    if content.get("scenarios"):
        return True
    if content.get("constraints"):
        return True
    outlook = content.get("market_outlook") or {}
    if any(value not in {None, "UNCERTAIN"} for value in outlook.values()):
        return True
    if any(value is not None for value in (content.get("time_horizon") or {}).values()):
        return True
    for key in ("risk", "position_intent", "derivative_intent"):
        section = content.get(key) or {}
        if any(value is not None for value in section.values()):
            return True
    return False


def _classify_path(path: str) -> str:
    top = path.lstrip("/").split("/", 1)[0]
    return "MATERIAL" if top in MATERIAL_FIELDS else "MINOR"


def _diff(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        diffs: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}/{key}"
            if key not in before:
                diffs.append(
                    {"op": "add", "path": child, "before": None, "after": after[key]}
                )
            elif key not in after:
                diffs.append(
                    {"op": "remove", "path": child, "before": before[key], "after": None}
                )
            else:
                diffs.extend(_diff(before[key], after[key], child))
        return diffs
    if isinstance(before, list) and isinstance(after, list):
        if before == after:
            return []
        return [
            {
                "op": "replace",
                "path": path or "/",
                "before": before,
                "after": after,
            }
        ]
    if before != after:
        return [
            {
                "op": "replace",
                "path": path or "/",
                "before": before,
                "after": after,
            }
        ]
    return []


def build_diff(
    previous: dict[str, Any] | None, current: ThesisContent
) -> tuple[str, list[dict[str, Any]]]:
    before = normalized_content(content_from_dict(previous))
    after = normalized_content(current)
    diffs = _diff(before, after)
    for item in diffs:
        item["classification"] = _classify_path(str(item["path"]))
    if any(item["classification"] == "MATERIAL" for item in diffs):
        return "MATERIAL", diffs
    if previous is None and _is_meaningful_material(after):
        return "MATERIAL", diffs
    return "MINOR", diffs