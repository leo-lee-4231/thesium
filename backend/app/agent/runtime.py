import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import ContextError, build_monitor_context, source_list
from app.agent.prompts import SYSTEM_PROMPT, monitor_user_prompt
from app.application.llm_provider_service import LLMProviderService
from app.application.market_service import MarketService
from app.db.models import AgentRun, InvestmentDecision
from app.domain.decision import DecisionOutput, validate_decision
from app.infrastructure.llm.client import LLMClient, LLMError, LLMNotConfigured


class AgentError(Exception):
    def __init__(self, code: str, message: str, run_id: UUID | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.run_id = run_id


class AgentRuntime:
    def __init__(self, session: AsyncSession, market: MarketService) -> None:
        self._session = session
        self._market = market
        self._llm_config = LLMProviderService(session)

    async def run_monitor(self, stream_id: UUID) -> dict[str, object]:
        config = await self._llm_config.config()
        if config is None:
            raise AgentError(
                "LLM_NOT_CONFIGURED", "configure an LLM provider in Settings first"
            )
        provider_row = await self._llm_config.current()
        try:
            ctx = await build_monitor_context(self._session, self._market, stream_id)
        except ContextError as exc:
            raise AgentError(exc.code, exc.message) from exc

        thesis = ctx.thesis
        context = ctx.context
        digest = ctx.digest
        ctx.stream.last_monitored_at = datetime.now(UTC)
        await self._session.commit()

        run = AgentRun(
            stream_id=stream_id,
            task_type="MONITOR_ANALYSIS",
            status="RUNNING",
            llm_provider_id=provider_row.id if provider_row else None,
            model=config.model,
            prompt_version="system.v1+monitor.v1",
            thesis_version_id=thesis.id if thesis is not None else None,
            position_snapshot_id=ctx.position_snapshot.id if ctx.position_snapshot else None,
            derivative_snapshot_id=ctx.derivative_snapshot.id if ctx.derivative_snapshot else None,
            market_snapshot_id=ctx.market_snapshot.id if ctx.market_snapshot else None,
            input_digest=digest,
            input_context=context,
            tool_calls=source_list(ctx),
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)

        started = time.monotonic()
        client = LLMClient(config)
        try:
            parsed = await client.chat_json(SYSTEM_PROMPT, monitor_user_prompt(context))
            output = DecisionOutput.model_validate(parsed)
            derivative_state = (ctx.derivative_position or {}).get("state") or {}
            thesis_content = (thesis.structured_content or {}) if thesis else {}
            derivative_intent = thesis_content.get("derivative_intent") or {}
            errors = validate_decision(
                output,
                has_thesis=thesis is not None,
                has_derivative=ctx.derivative_position is not None,
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
        return {"run": run, "decision": decision, "context": context}

    async def _fail_run(self, run: AgentRun, code: str, message: str) -> None:
        run.status = "FAILED"
        run.error_code = code
        run.error_message = message[:2000]
        run.finished_at = datetime.now(UTC)
        await self._session.commit()