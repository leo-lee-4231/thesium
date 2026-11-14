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
    description: str | None = None


class KeyLevels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    support: list[str] = Field(default_factory=list)
    resistance: list[str] = Field(default_factory=list)
    watch: list[str] = Field(default_factory=list)


class RiskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_equity_usd: str | None = None
    max_drawdown_pct: str | None = None
    max_position_pct: str | None = None
    max_risk_per_trade_pct: str | None = None
    max_concurrent_positions: str | None = None
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
    long_stop_loss_price: str | None = None
    short_stop_loss_price: str | None = None


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

_OUTLOOKS = {"BULLISH", "NEUTRAL", "BEARISH", "UNCERTAIN"}
_HORIZONS = {"DAYS", "WEEKS", "MONTHS", "YEARS"}
_DIRECTIONS = {"UP", "DOWN", "RANGE"}
_SCENARIO_HORIZONS = {"SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"}
_SCENARIO_STATUSES = {"USER_EXPECTATION", "CONDITIONAL"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _as_enum(value: Any, allowed: set[str]) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper().replace("-", "_").replace(" ", "_")
    return candidate if candidate in allowed else None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def normalize_draft(draft: Any) -> dict[str, Any]:
    """Coerce common LLM output shapes into the strict ThesisContent schema.

    This is only used for AI parse drafts; manual submissions remain strict.
    """
    if not isinstance(draft, dict):
        return {}

    allowed_top = set(ThesisContent.model_fields)
    data = {key: value for key, value in draft.items() if key in allowed_top}
    data["schema_version"] = str(data.get("schema_version") or "1.0")

    for key in ("thesis_statement", "purpose", "notes"):
        if key in data:
            data[key] = _as_str(data.get(key))

    horizon_raw = _as_dict(data.get("time_horizon"))
    horizon = {
        key: _as_enum(horizon_raw.get(key), _HORIZONS)
        for key in ("short_term", "medium_term", "long_term")
        if _as_enum(horizon_raw.get(key), _HORIZONS) is not None
    }
    data["time_horizon"] = horizon

    outlook_raw = _as_dict(data.get("market_outlook"))
    data["market_outlook"] = {
        key: _as_enum(outlook_raw.get(key), _OUTLOOKS) or "UNCERTAIN"
        for key in ("short_term", "medium_term", "long_term")
    }

    scenarios: list[dict[str, Any]] = []
    allowed_scenario = set(Scenario.model_fields)
    for index, raw in enumerate(_as_list(data.get("scenarios"))):
        if not isinstance(raw, dict):
            continue
        direction = _as_enum(raw.get("direction"), _DIRECTIONS)
        if direction is None:
            continue
        item = {key: value for key, value in raw.items() if key in allowed_scenario}
        item["id"] = _as_str(item.get("id")) or f"S{index + 1}"
        item["direction"] = direction
        item["target_price"] = _as_str(item.get("target_price"))
        item["target_currency"] = _as_str(item.get("target_currency")) or "USDT"
        item["time_horizon"] = (
            _as_enum(item.get("time_horizon"), _SCENARIO_HORIZONS) or "SHORT_TERM"
        )
        item["status"] = (
            _as_enum(item.get("status"), _SCENARIO_STATUSES) or "USER_EXPECTATION"
        )
        item["conditions"] = [str(value) for value in _as_list(item.get("conditions")) if value]
        item["invalidation"] = _as_str(item.get("invalidation"))
        item["description"] = _as_str(item.get("description"))
        scenarios.append(item)
    data["scenarios"] = scenarios

    levels_raw = _as_dict(data.get("key_levels"))
    data["key_levels"] = {
        key: [str(value) for value in _as_list(levels_raw.get(key)) if value not in (None, "")]
        for key in ("support", "resistance", "watch")
    }

    risk_raw = _as_dict(data.get("risk"))
    data["risk"] = {
        key: _as_str(risk_raw.get(key))
        for key in RiskProfile.model_fields
        if _as_str(risk_raw.get(key)) is not None
    }

    position_raw = _as_dict(data.get("position_intent"))
    data["position_intent"] = {
        "preferred_position_pct": _as_str(position_raw.get("preferred_position_pct")),
        "allow_add": _as_bool(position_raw.get("allow_add")),
        "allow_reduce": _as_bool(position_raw.get("allow_reduce")),
        "avoid_full_exit": _as_bool(position_raw.get("avoid_full_exit")),
    }
    data["position_intent"] = {
        key: value for key, value in data["position_intent"].items() if value is not None
    }

    derivative_raw = _as_dict(data.get("derivative_intent"))
    data["derivative_intent"] = {
        "allow_perpetual": _as_bool(derivative_raw.get("allow_perpetual")),
        "allow_short": _as_bool(derivative_raw.get("allow_short")),
        "max_leverage": _as_str(derivative_raw.get("max_leverage")),
        "max_margin_usd": _as_str(derivative_raw.get("max_margin_usd")),
        "min_liquidation_buffer_pct": _as_str(
            derivative_raw.get("min_liquidation_buffer_pct")
        ),
        "long_stop_loss_price": _as_str(derivative_raw.get("long_stop_loss_price")),
        "short_stop_loss_price": _as_str(derivative_raw.get("short_stop_loss_price")),
    }
    data["derivative_intent"] = {
        key: value for key, value in data["derivative_intent"].items() if value is not None
    }

    data["constraints"] = [
        str(value) for value in _as_list(data.get("constraints")) if value not in (None, "")
    ]
    data["open_questions"] = [
        str(value) for value in _as_list(data.get("open_questions")) if value not in (None, "")
    ]
    return data
