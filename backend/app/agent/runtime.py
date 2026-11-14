import hashlib
import json
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import SYSTEM_PROMPT, monitor_user_prompt
from app.application.llm_provider_service import LLMProviderService
from app.application.market_service import MarketService
from app.application.portfolio_service import PortfolioService
from app.application.thesis_service import ThesisService
from app.db.models import (
    AgentRun,
    Asset,
    DerivativePositionSnapshot,
    Instrument,
    InvestmentDecision,
    InvestmentStream,
    InvestmentThesis,
    MarketSnapshot,
    PositionSnapshot,
)
from app.domain.decision import DecisionOutput, validate_decision
from app.domain.risk import RiskError, StopLossInput, derive_stop_loss
from app.infrastructure.llm.client import LLMClient, LLMError, LLMNotConfigured
from app.infrastructure.market.base import Timeframe


class AgentError(Exception):
    def __init__(self, code: str, message: str, run_id: UUID | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.run_id = run_id


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _quote_dict(quote: object) -> dict[str, object]:
    return {
        "instrument": quote.instrument,  # type: ignore[attr-defined]
        "price": str(quote.price),  # type: ignore[attr-defined]
        "change_24h_pct": str(quote.change_24h_pct)  # type: ignore[attr-defined]
        if quote.change_24h_pct is not None  # type: ignore[attr-defined]
        else None,
        "high_24h": str(quote.high_24h) if quote.high_24h is not None else None,  # type: ignore[attr-defined]
        "low_24h": str(quote.low_24h) if quote.low_24h is not None else None,  # type: ignore[attr-defined]
        "volume_24h": str(quote.volume_24h) if quote.volume_24h is not None else None,  # type: ignore[attr-defined]
        "market_time": quote.market_time.isoformat(),  # type: ignore[attr-defined]
        "fetched_at": quote.fetched_at.isoformat(),  # type: ignore[attr-defined]
        "staleness": quote.staleness,  # type: ignore[attr-defined]
        "source": quote.source,  # type: ignore[attr-defined]
    }


def _derivatives_dict(overview: object) -> dict[str, object]:
    return {
        "instrument": overview.instrument,  # type: ignore[attr-defined]
        "mark_price": str(overview.mark_price),  # type: ignore[attr-defined]
        "funding_rate": str(overview.funding_rate)  # type: ignore[attr-defined]
        if overview.funding_rate is not None  # type: ignore[attr-defined]
        else None,
        "next_funding_time": overview.next_funding_time.isoformat()  # type: ignore[attr-defined]
        if overview.next_funding_time  # type: ignore[attr-defined]
        else None,
        "open_interest": str(overview.open_interest)  # type: ignore[attr-defined]
        if overview.open_interest is not None  # type: ignore[attr-defined]
        else None,
        "market_time": overview.market_time.isoformat(),  # type: ignore[attr-defined]
        "staleness": overview.staleness,  # type: ignore[attr-defined]
    }


def _thesis_dict(thesis: InvestmentThesis) -> dict[str, object]:
    return {
        "id": str(thesis.id),
        "version": thesis.version,
        "original_text": thesis.original_text,
        "final_text": thesis.final_text or thesis.original_text,
        "structured_content": thesis.structured_content,
        "effective_from": thesis.effective_from.isoformat(),
    }


def _risk_plan(
    thesis: InvestmentThesis | None, derivative: dict | None
) -> dict[str, object] | None:
    if thesis is None or derivative is None:
        return None
    content = thesis.structured_content or {}
    risk = content.get("risk") or {}
    intent = content.get("derivative_intent") or {}
    state = derivative.get("state") or {}
    side = str(state.get("side", ""))
    if side not in {"LONG", "SHORT"}:
        return None

    equity = _decimal(risk.get("account_equity_usd"))
    max_drawdown = _decimal(risk.get("max_drawdown_pct"))
    if equity is None or max_drawdown is None:
        return {"error": "missing risk.account_equity_usd or max_drawdown_pct"}

    explicit = _decimal(
        intent.get("long_stop_loss_price")
        if side == "LONG"
        else intent.get("short_stop_loss_price")
    ) or _decimal(risk.get("stop_loss_price"))

    try:
        return derive_stop_loss(
            StopLossInput(
                side=side,
                entry_price=_decimal(state.get("entry_price")) or Decimal("0"),
                quantity_base=_decimal(state.get("quantity_base")) or Decimal("0"),
                account_equity_usd=equity,
                max_drawdown_pct=max_drawdown,
                max_concurrent_positions=_int(risk.get("max_concurrent_positions"), 5),
                max_risk_per_trade_pct=_decimal(risk.get("max_risk_per_trade_pct")),
                risk_budget_usd=_decimal(risk.get("risk_budget_usd")),
                explicit_stop=explicit,
                liquidation_price=_decimal(state.get("liquidation_price")),
            )
        )
    except RiskError as exc:
        return {"error": exc.message}


class AgentRuntime:
    def __init__(self, session: AsyncSession, market: MarketService) -> None:
        self._session = session
        self._market = market
        self._thesis = ThesisService(session)
        self._portfolio = PortfolioService(session)
        self._llm_config = LLMProviderService(session)

    async def _stream(self, stream_id: UUID) -> tuple[InvestmentStream, Asset]:
        stream = await self._session.get(InvestmentStream, stream_id)
        if stream is None:
            raise AgentError("NOT_FOUND", "investment stream not found")
        asset = await self._session.get(Asset, stream.asset_id)
        if asset is None:
            raise AgentError("NOT_FOUND", "asset not found")
        return stream, asset

    async def run_monitor(self, stream_id: UUID) -> dict[str, object]:
        stream, asset = await self._stream(stream_id)
        config = await self._llm_config.config()
        if config is None:
            raise AgentError(
                "LLM_NOT_CONFIGURED", "configure an LLM provider in Settings first"
            )
        provider_row = await self._llm_config.current()
        thesis = await self._thesis.active(stream_id)

        try:
            quote = await self._market.quote(asset.symbol, "SPOT")
        except Exception as exc:
            raise AgentError("MARKET_UNAVAILABLE", f"spot market unavailable: {exc}") from exc
        indicators = await self._market.indicators(
            asset.symbol, [Timeframe.H1, Timeframe.H4, Timeframe.D1], "SPOT"
        )
        derivatives = None
        try:
            derivatives = await self._market.derivatives(asset.symbol)
        except Exception:
            derivatives = None

        perp_mark = derivatives.mark_price if derivatives is not None else None
        spot_position = await self._portfolio.spot(stream_id, quote.price)
        derivative_position = await self._portfolio.derivative(stream_id, perp_mark)
        risk_plan = _risk_plan(thesis, derivative_position)

        recent = await self._session.execute(
            select(InvestmentDecision)
            .where(InvestmentDecision.stream_id == stream_id)
            .order_by(InvestmentDecision.created_at.desc())
            .limit(3)
        )
        recent_decisions = [
            {
                "decision": decision.decision,
                "summary": decision.summary,
                "priority": decision.priority,
                "alignment": (decision.thesis_alignment or {}).get("status"),
                "created_at": decision.created_at.isoformat(),
            }
            for decision in recent.scalars().all()
        ]

        context = {
            "stream": {
                "id": str(stream.id),
                "name": stream.name,
                "timezone": stream.timezone,
                "monitor_interval_minutes": stream.monitor_interval_minutes,
            },
            "asset": {"symbol": asset.symbol, "name": asset.name, "kind": asset.kind},
            "market": {
                "quote": _quote_dict(quote),
                "indicators": indicators,
                "derivatives": _derivatives_dict(derivatives) if derivatives else None,
            },
            "thesis": _thesis_dict(thesis) if thesis is not None else None,
            "has_thesis": thesis is not None,
            "spot": spot_position,
            "derivative": derivative_position,
            "risk_plan": risk_plan,
            "recent_decisions": recent_decisions,
            "data_quality": {
                "quote_staleness": quote.staleness,
                "derivatives_staleness": derivatives.staleness if derivatives else None,
            },
        }
        digest = hashlib.sha256(
            json.dumps(context, sort_keys=True, default=str, ensure_ascii=False).encode()
        ).hexdigest()

        instrument = await self._session.get(Instrument, stream.primary_instrument_id)
        market_snapshot = (
            await self._session.scalar(
                select(MarketSnapshot)
                .where(MarketSnapshot.instrument_id == instrument.id)
                .order_by(MarketSnapshot.created_at.desc())
                .limit(1)
            )
            if instrument is not None
            else None
        )
        position_snapshot = await self._session.scalar(
            select(PositionSnapshot)
            .where(PositionSnapshot.stream_id == stream_id)
            .order_by(PositionSnapshot.created_at.desc())
            .limit(1)
        )
        derivative_snapshot = await self._session.scalar(
            select(DerivativePositionSnapshot)
            .where(DerivativePositionSnapshot.stream_id == stream_id)
            .order_by(DerivativePositionSnapshot.created_at.desc())
            .limit(1)
        )

        run = AgentRun(
            stream_id=stream_id,
            task_type="MONITOR_ANALYSIS",
            status="RUNNING",
            llm_provider_id=provider_row.id if provider_row else None,
            model=config.model,
            prompt_version="system.v1+monitor.v1",
            thesis_version_id=thesis.id if thesis is not None else None,
            position_snapshot_id=position_snapshot.id if position_snapshot else None,
            derivative_snapshot_id=derivative_snapshot.id if derivative_snapshot else None,
            market_snapshot_id=market_snapshot.id if market_snapshot else None,
            input_digest=digest,
            input_context=context,
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)

        started = time.monotonic()
        client = LLMClient(config)
        try:
            parsed = await client.chat_json(SYSTEM_PROMPT, monitor_user_prompt(context))
            output = DecisionOutput.model_validate(parsed)
            derivative_state = (derivative_position or {}).get("state") or {}
            thesis_content = (thesis.structured_content or {}) if thesis else {}
            derivative_intent = thesis_content.get("derivative_intent") or {}
            errors = validate_decision(
                output,
                has_thesis=thesis is not None,
                has_derivative=derivative_position is not None,
                derivative_side=derivative_state.get("side"),
                allow_short=derivative_intent.get("allow_short"),
            )
            if errors:
                raise AgentError("SCHEMA_INVALID", "; ".join(errors), run.id)
        except AgentError as exc:
            await self._fail_run(run, exc.code, exc.message)
            raise
        except ValidationError as exc:
            await self._fail_run(run, "SCHEMA_INVALID", str(exc))
            raise AgentError("SCHEMA_INVALID", f"invalid decision JSON: {exc}", run.id) from exc
        except LLMNotConfigured as exc:
            await self._fail_run(run, "LLM_NOT_CONFIGURED", str(exc))
            raise AgentError("LLM_NOT_CONFIGURED", str(exc), run.id) from exc
        except LLMError as exc:
            await self._fail_run(run, exc.code, exc.message)
            raise AgentError(exc.code, exc.message, run.id) from exc
        except Exception as exc:
            await self._fail_run(run, "AGENT_ERROR", str(exc))
            raise AgentError("AGENT_ERROR", str(exc), run.id) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        parsed_json = output.model_dump(mode="json")
        decision = InvestmentDecision(
            stream_id=stream_id,
            agent_run_id=run.id,
            schema_version=output.schema_version,
            decision=output.decision,
            confidence=Decimal(str(output.confidence)),
            priority=output.priority,
            summary=output.summary,
            evidence_for=parsed_json["evidence_for"],
            evidence_against=parsed_json["evidence_against"],
            thesis_alignment=parsed_json["thesis_alignment"],
            position_impact=parsed_json["position_impact"],
            derivative_recommendation=parsed_json.get("derivative_recommendation"),
            changes_since_previous=parsed_json["changes_since_previous"],
            invalidation_conditions=parsed_json["invalidation_conditions"],
            data_quality=parsed_json["data_quality"],
            notification_recommendation=parsed_json["notification_recommendation"],
        )
        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)
        run.latency_ms = latency_ms
        run.output_raw = json.dumps(parsed_json, ensure_ascii=False)
        run.output_parsed = parsed_json
        self._session.add(decision)
        await self._session.commit()
        await self._session.refresh(run)
        await self._session.refresh(decision)
        return {"run": run, "decision": decision}

    async def _fail_run(self, run: AgentRun, code: str, message: str) -> None:
        run.status = "FAILED"
        run.error_code = code
        run.error_message = message[:2000]
        run.finished_at = datetime.now(UTC)
        await self._session.commit()