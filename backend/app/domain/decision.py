from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DecisionEnum = Literal["BUY", "SELL", "HOLD", "REDUCE", "WAIT", "REVIEW"]
PriorityEnum = Literal["LOW", "NORMAL", "HIGH", "URGENT"]
AlignmentEnum = Literal["ALIGNED", "PARTIALLY_ALIGNED", "CONFLICTING", "UNKNOWN"]
DataQualityEnum = Literal["GOOD", "DEGRADED", "INSUFFICIENT"]
DerivativeAction = Literal[
    "OPEN_LONG",
    "INCREASE_LONG",
    "REDUCE_LONG",
    "CLOSE_LONG",
    "OPEN_SHORT",
    "INCREASE_SHORT",
    "REDUCE_SHORT",
    "CLOSE_SHORT",
    "ADJUST_MARGIN",
    "HOLD",
    "NONE",
]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claim: str
    kind: Literal["FACT", "INFERENCE"] = "FACT"
    source_tool: str = ""
    as_of: str | None = None
    strength: Literal["STRONG", "MODERATE", "WEAK"] = "MODERATE"

    @field_validator("strength", mode="before")
    @classmethod
    def normalize_strength(cls, value: object) -> object:
        """Accept common LLM synonyms without weakening the stored schema."""
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "HIGH": "STRONG",
            "VERY_HIGH": "STRONG",
            "MEDIUM": "MODERATE",
            "NORMAL": "MODERATE",
            "LOW": "WEAK",
            "VERY_LOW": "WEAK",
        }
        return aliases.get(normalized, normalized)


class ThesisAlignment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: AlignmentEnum = "UNKNOWN"
    explanation: str = ""
    conflicting_fields: list[str] = Field(default_factory=list)


class PositionImpact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    assessment: Literal[
        "NO_POSITION",
        "EXISTING_POSITION_ALIGNED",
        "EXISTING_POSITION_EXPOSED_TO_DOWNSIDE",
        "EXISTING_POSITION_UNDERUTILIZED",
        "RISK_BUDGET_EXCEEDED",
    ] = "NO_POSITION"
    exposure_usd: str | None = None
    unrealized_pnl_usd: str | None = None
    risk_budget_usage_pct: str | None = None
    notes: str | None = None

    @field_validator("assessment", mode="before")
    @classmethod
    def normalize_assessment(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "NO_POSITION_NO_EXPOSURE": "NO_POSITION",
            "NO_EXPOSURE": "NO_POSITION",
            "FLAT": "NO_POSITION",
            "POSITION_ALIGNED": "EXISTING_POSITION_ALIGNED",
            "EXISTING_POSITION": "EXISTING_POSITION_ALIGNED",
            "POSITION_EXPOSED": "EXISTING_POSITION_EXPOSED_TO_DOWNSIDE",
            "POSITION_UNDERUTILIZED": "EXISTING_POSITION_UNDERUTILIZED",
        }
        return aliases.get(normalized, normalized)


class StopLossPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    price: str
    source: Literal["USER", "DERIVED"]
    risk_amount_usd: str | None = None
    risk_pct_equity: str | None = None
    distance_pct: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DerivativeRecommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: DerivativeAction
    size_change_pct: str | None = None
    rationale: str = ""
    invalidation_conditions: list[Any] = Field(default_factory=list)
    stop_loss: StopLossPlan | None = None


class DataQuality(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: DataQualityEnum = "GOOD"
    missing: list[str] = Field(default_factory=list)
    staleness: str = "FRESH"
    as_of: str | None = None


class NotificationRecommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notify: bool = False
    reason: str | None = None
    suggested_priority: PriorityEnum | None = None


class DecisionOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = "v1"
    decision: DecisionEnum
    confidence: float = Field(ge=0, le=1)
    priority: PriorityEnum
    summary: str = Field(min_length=1, max_length=500)
    evidence_for: list[Evidence] = Field(default_factory=list)
    evidence_against: list[Evidence] = Field(default_factory=list)
    thesis_alignment: ThesisAlignment = Field(default_factory=ThesisAlignment)
    position_impact: PositionImpact = Field(default_factory=PositionImpact)
    derivative_recommendation: DerivativeRecommendation | None = None
    changes_since_previous: list[Any] = Field(default_factory=list)
    invalidation_conditions: list[Any] = Field(default_factory=list)
    data_quality: DataQuality = Field(default_factory=DataQuality)
    notification_recommendation: NotificationRecommendation = Field(
        default_factory=NotificationRecommendation
    )


def validate_decision(
    output: DecisionOutput,
    *,
    has_thesis: bool,
    has_derivative: bool,
    derivative_side: str | None,
    allow_short: bool | None,
) -> list[str]:
    errors: list[str] = []

    if not has_thesis:
        if output.decision not in {"WAIT", "REVIEW"}:
            errors.append("without an ACTIVE thesis decision must be WAIT or REVIEW")
        if output.thesis_alignment.status != "UNKNOWN":
            errors.append("without an ACTIVE thesis thesis_alignment.status must be UNKNOWN")

    if output.data_quality.status == "INSUFFICIENT":
        if output.decision not in {"WAIT", "REVIEW"}:
            errors.append("data_quality=INSUFFICIENT requires decision WAIT or REVIEW")
        if output.confidence > 0.5:
            errors.append("data_quality=INSUFFICIENT requires confidence <= 0.5")
        if output.notification_recommendation.notify:
            errors.append("data_quality=INSUFFICIENT cannot notify")

    if has_derivative and output.derivative_recommendation is None:
        errors.append("derivative_recommendation is required when a perpetual position exists")

    recommendation = output.derivative_recommendation
    if recommendation is not None:
        action = recommendation.action
        long_actions = {"INCREASE_LONG", "REDUCE_LONG", "CLOSE_LONG", "ADJUST_MARGIN"}
        short_actions = {"INCREASE_SHORT", "REDUCE_SHORT", "CLOSE_SHORT", "ADJUST_MARGIN"}
        if has_derivative:
            if derivative_side == "LONG" and action not in long_actions | {"HOLD"}:
                errors.append(f"action {action} does not match LONG position")
            if derivative_side == "SHORT" and action not in short_actions | {"HOLD"}:
                errors.append(f"action {action} does not match SHORT position")
        else:
            if action not in {"NONE", "OPEN_LONG", "OPEN_SHORT"}:
                errors.append(f"action {action} requires an existing position")
            if action == "OPEN_SHORT" and allow_short is False:
                errors.append("thesis derivative_intent.allow_short=false forbids OPEN_SHORT")

        if (
            action in {"OPEN_LONG", "OPEN_SHORT", "INCREASE_LONG", "INCREASE_SHORT"}
            and recommendation.stop_loss is None
        ):
            errors.append(
                "stop_loss is required for OPEN_LONG/OPEN_SHORT/INCREASE_LONG/INCREASE_SHORT"
            )

    return errors