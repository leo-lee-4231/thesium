# ruff: noqa: E501
import re
from typing import Any

from app.domain.thesis import (
    ThesisContent,
    ThesisValidationError,
    content_from_dict,
    normalize_draft,
    normalized_content,
)
from app.infrastructure.llm.client import LLMClient, LLMError

POLISH_SYSTEM = """你是投资论点的文字编辑，不是投资顾问。
只改善表达、结构、清晰度；不得新增或删除数字、目标价、方向、周期、约束或事实。
不得把用户观点改写成投资建议；不得加入原文没有的确定性；保持第一人称与原文语言。
输出 JSON：{"polished_text": string, "change_notes": [{"kind": string, "before": string, "after": string, "reason": string}], "warnings": [string], "meaning_preserved": boolean}。
如果原文已经足够清晰，polished_text 返回原文，change_notes 为空。"""

PARSE_SYSTEM = """你是投资论点结构化助手，不是投资顾问。
把用户原话整理为草案，不新增用户没说的目标价、方向、风险数字或策略；不确定的字段留空。
输出 JSON：{"draft": {...}, "unparsed": [{"text": string, "reason": string}], "clarifying_questions": [string], "warnings": [string]}。
draft 字段：schema_version, thesis_statement, purpose, time_horizon{short_term,medium_term,long_term},
market_outlook{short_term,medium_term,long_term}, scenarios[], key_levels{support,resistance,watch},
risk{account_equity_usd,max_drawdown_pct,max_position_pct,max_risk_per_trade_pct,max_concurrent_positions,risk_budget_usd,stop_loss_price,take_profit_price},
position_intent{preferred_position_pct,allow_add,allow_reduce,avoid_full_exit},
derivative_intent{allow_perpetual,allow_short,max_leverage,max_margin_usd,min_liquidation_buffer_pct,long_stop_loss_price,short_stop_loss_price},
constraints[], open_questions[], notes。
枚举：time_horizon 用 DAYS/WEEKS/MONTHS/YEARS；outlook 用 BULLISH/NEUTRAL/BEARISH/UNCERTAIN；
scenario.direction 用 UP/DOWN/RANGE；scenario.time_horizon 用 SHORT_TERM/MEDIUM_TERM/LONG_TERM。
金额/价格用字符串。

澄清规则（只清理原文歧义，不做需求审查）：
- 只列用户原话中真正影响理解的歧义：指代不明、同一术语多种含义、明显自相矛盾。最多 3 条；没有就返回 []。
- 不要要求用户预测未来、补全未提供的参数，或把模糊表达变成精确数字。禁止问「短期具体到哪一天/多少周」「未来价格是多少」「仓位比例/杠杆/止损是多少」。
- 时间/价格/情景保持用户原样；能用枚举近似就用枚举，不能判断就留空或写进 unparsed/notes，不要追问。
- 本产品 v1 只支持 USDT 本位永续；不要问现货借币、交割、期权或具体下单工具。
- 未提及的风险参数、仓位细节、执行工具不要问；这些在实际分析/策略阶段再确认。
- 不要重复问用户已经写清楚的信息；能通过 unparsed/warnings 表达的，不要硬塞成问题。"""

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_DIRECTION_WORDS = {"看涨", "看跌", "中性", "做多", "做空", "加仓", "减仓", "清仓", "持有"}


def _numbers(text: str) -> set[str]:
    return {match.replace(",", "") for match in _NUMBER.findall(text)}


def _directions(text: str) -> set[str]:
    return {word for word in _DIRECTION_WORDS if word in text}


class ThesisAI:
    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()

    async def polish(self, text: str) -> dict[str, Any]:
        result = await self._client.chat_json(
            POLISH_SYSTEM,
            f"原文：\n{text}\n\n请只润色表达，返回 JSON。",
        )
        polished = result.get("polished_text")
        if not isinstance(polished, str) or not polished.strip():
            raise LLMError("LLM_BAD_RESPONSE", "missing polished_text")
        warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        if _numbers(text) != _numbers(polished):
            warnings.append("润色前后数字集合不一致，请人工核对")
        if _directions(text) != _directions(polished):
            warnings.append("润色前后方向/动作词不一致，请人工核对")
        return {
            "polished_text": polished,
            "change_notes": result.get("change_notes") or [],
            "warnings": warnings,
            "meaning_preserved": bool(result.get("meaning_preserved", False)),
        }

    async def parse(self, text: str) -> dict[str, Any]:
        result = await self._client.chat_json(
            PARSE_SYSTEM,
            f"用户原话：\n{text}\n\n只整理，不新增；返回 JSON。",
        )
        draft = result.get("draft")
        if not isinstance(draft, dict):
            raise LLMError("LLM_BAD_RESPONSE", "missing draft")
        try:
            content: ThesisContent = content_from_dict(normalize_draft(draft))
        except ThesisValidationError as exc:
            raise LLMError("LLM_BAD_RESPONSE", str(exc)) from exc
        questions = result.get("clarifying_questions") or []
        if not isinstance(questions, list):
            questions = []
        cleaned_questions = [str(question).strip() for question in questions if str(question).strip()]
        return {
            "draft": normalized_content(content),
            "unparsed": result.get("unparsed") or [],
            "clarifying_questions": cleaned_questions[:3],
            "warnings": result.get("warnings") or [],
        }
