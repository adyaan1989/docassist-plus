"""
Intent & Emotion Detection Service
====================================
Two-stage detection:
  1. Fast rule-based classifier (zero-cost, low-latency)
  2. LLM-based classifier (used only when rule-based confidence is low)

Intent classes  : question, complaint, request, feedback, check_status, general_query, unknown
Emotion classes : happy, neutral, frustrated, angry
"""

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from backend.config.settings import settings
from backend.models.schemas import Emotion, Intent, ResponseTone
from backend.utils.logger import setup_logger

logger = setup_logger(__name__)


# ── Rule-based patterns ───────────────────────────────────────────────────────

INTENT_PATTERNS: Dict[Intent, List[str]] = {
    Intent.QUESTION: [
        r"\bwhat\b", r"\bwhen\b", r"\bwhere\b", r"\bwho\b", r"\bhow\b",
        r"\bwhy\b", r"\bis there\b", r"\bcan you\b", r"\bcould you tell\b",
        r"\bdo you\b", r"\bdoes\b", r"\?",
    ],
    Intent.COMPLAINT: [
        r"\bthis is ridiculous\b", r"\bunacceptable\b", r"\bstill not\b",
        r"\bnot working\b", r"\bbroken\b", r"\bterrible\b", r"\bbad\b",
        r"\bdisappointed\b", r"\bfailed\b", r"\bnot received\b",
        r"\bI want to complain\b", r"\bI am upset\b",
    ],
    Intent.REQUEST: [
        r"\bplease\b", r"\bcould you\b", r"\bI need\b", r"\bI want\b",
        r"\bI would like\b", r"\bhelp me\b", r"\bsend me\b", r"\bprovide\b",
        r"\bI require\b",
    ],
    Intent.FEEDBACK: [
        r"\bgreat\b", r"\bexcellent\b", r"\blove it\b", r"\bsuggestion\b",
        r"\bfeedback\b", r"\bimprove\b", r"\bthank you\b", r"\bthanks\b",
        r"\bworse\b", r"\bbetter\b",
    ],
    Intent.CHECK_STATUS: [
        r"\bstatus\b", r"\bcheck\b", r"\btrack\b", r"\bwhere is\b",
        r"\bupdate\b", r"\bprogress\b", r"\bhas my\b", r"\bloan\b",
        r"\border\b", r"\brefund\b", r"\bdelivery\b",
    ],
}

EMOTION_PATTERNS: Dict[Emotion, List[str]] = {
    Emotion.ANGRY: [
        r"\bfurious\b", r"\banger\b", r"\bangry\b", r"\boutrageous\b",
        r"\bthis is ridiculous\b", r"\bunacceptable\b", r"!\s*!", r"\bwhat the\b",
        r"\bI demand\b", r"\bimmediately\b",
    ],
    Emotion.FRUSTRATED: [
        r"\bfrustrated\b", r"\bstill\b.*\bnot\b", r"\bwhy is it\b",
        r"\bkeep waiting\b", r"\bagain\b", r"\bnot fixed\b", r"\bsame issue\b",
        r"\btired of\b", r"\bno response\b",
    ],
    Emotion.HAPPY: [
        r"\bthank you\b", r"\bthanks\b", r"\bgreat\b", r"\bperfect\b",
        r"\bexcellent\b", r"\blove\b", r"\bhappy\b", r"\bwonderful\b",
        r"\bawesome\b", r"\bappreciate\b",
    ],
}

# Tone mapping matrix
TONE_MATRIX: Dict[Tuple[Intent, Emotion], ResponseTone] = {
    (Intent.COMPLAINT, Emotion.ANGRY): ResponseTone.APOLOGETIC,
    (Intent.COMPLAINT, Emotion.FRUSTRATED): ResponseTone.EMPATHETIC,
    (Intent.COMPLAINT, Emotion.NEUTRAL): ResponseTone.FORMAL,
    (Intent.QUESTION, Emotion.HAPPY): ResponseTone.FRIENDLY,
    (Intent.QUESTION, Emotion.NEUTRAL): ResponseTone.FORMAL,
    (Intent.REQUEST, Emotion.NEUTRAL): ResponseTone.FORMAL,
    (Intent.FEEDBACK, Emotion.HAPPY): ResponseTone.FRIENDLY,
    (Intent.CHECK_STATUS, Emotion.FRUSTRATED): ResponseTone.EMPATHETIC,
    (Intent.CHECK_STATUS, Emotion.NEUTRAL): ResponseTone.FORMAL,
}
DEFAULT_TONE = ResponseTone.FORMAL


@dataclass
class DetectionResult:
    label: str
    confidence: float
    is_low_confidence: bool
    method: str  # "rule" | "llm"


class IntentEmotionDetector:
    """
    Hybrid detector: rule-based (fast) → LLM fallback (accurate).
    """

    INTENT_SYSTEM_PROMPT = """You are an intent classifier. Given a user message, 
classify the intent into exactly one of: question, complaint, request, feedback, 
check_status, general_query, unknown.

Respond with JSON only:
{"intent": "<label>", "confidence": <0.0-1.0>}"""

    EMOTION_SYSTEM_PROMPT = """You are an emotion classifier. Given a user message, 
classify the emotion into exactly one of: happy, neutral, frustrated, angry.

Respond with JSON only:
{"emotion": "<label>", "confidence": <0.0-1.0>}"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.intent_threshold = settings.INTENT_CONFIDENCE_THRESHOLD
        self.emotion_threshold = settings.EMOTION_CONFIDENCE_THRESHOLD

    # ── Public API ────────────────────────────────────────────────────────

    async def detect(self, text: str) -> Tuple[DetectionResult, DetectionResult]:
        """Returns (intent_result, emotion_result)."""
        intent_result = self._rule_based_intent(text)
        emotion_result = self._rule_based_emotion(text)

        # Fallback to LLM if confidence below threshold
        tasks = []
        if intent_result.confidence < self.intent_threshold:
            logger.debug(f"Low intent confidence ({intent_result.confidence:.2f}) → LLM fallback")
            tasks.append(("intent", text))

        if emotion_result.confidence < self.emotion_threshold:
            logger.debug(f"Low emotion confidence ({emotion_result.confidence:.2f}) → LLM fallback")
            tasks.append(("emotion", text))

        # Call LLM for fallbacks (in parallel)
        if tasks:
            import asyncio
            results = await asyncio.gather(
                *[self._llm_detect(task_type, t) for task_type, t in tasks],
                return_exceptions=True,
            )
            for (task_type, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.warning(f"LLM fallback failed for {task_type}: {result}")
                    continue
                if task_type == "intent":
                    intent_result = result
                else:
                    emotion_result = result

        return intent_result, emotion_result

    def get_response_tone(self, intent: Intent, emotion: Emotion) -> ResponseTone:
        return TONE_MATRIX.get((intent, emotion), DEFAULT_TONE)

    # ── Rule-based ────────────────────────────────────────────────────────

    def _rule_based_intent(self, text: str) -> DetectionResult:
        lower = text.lower()
        scores: Dict[Intent, int] = {i: 0 for i in INTENT_PATTERNS}
        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower):
                    scores[intent] += 1

        best_intent = max(scores, key=lambda x: scores[x])
        total_patterns = len(INTENT_PATTERNS[best_intent])
        matches = scores[best_intent]

        if matches == 0:
            return DetectionResult(
                label=Intent.UNKNOWN.value,
                confidence=0.0,
                is_low_confidence=True,
                method="rule",
            )

        confidence = min(matches / max(total_patterns * 0.3, 1), 1.0)
        return DetectionResult(
            label=best_intent.value,
            confidence=round(confidence, 3),
            is_low_confidence=confidence < self.intent_threshold,
            method="rule",
        )

    def _rule_based_emotion(self, text: str) -> DetectionResult:
        lower = text.lower()
        scores: Dict[Emotion, int] = {e: 0 for e in EMOTION_PATTERNS}
        for emotion, patterns in EMOTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower):
                    scores[emotion] += 1

        best_emotion = max(scores, key=lambda x: scores[x])
        matches = scores[best_emotion]

        if matches == 0:
            return DetectionResult(
                label=Emotion.NEUTRAL.value,
                confidence=0.7,   # neutral is the safe default
                is_low_confidence=False,
                method="rule",
            )

        confidence = min(matches / 3.0, 1.0)
        return DetectionResult(
            label=best_emotion.value,
            confidence=round(confidence, 3),
            is_low_confidence=confidence < self.emotion_threshold,
            method="rule",
        )

    # ── LLM fallback ────────────────────────────────────────────────────

    async def _llm_detect(self, task_type: str, text: str) -> DetectionResult:
        import json

        system = (
            self.INTENT_SYSTEM_PROMPT
            if task_type == "intent"
            else self.EMOTION_SYSTEM_PROMPT
        )

        response = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Message: {text}"},
            ],
            max_tokens=50,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)

        label = data.get(task_type, "unknown" if task_type == "intent" else "neutral")
        confidence = float(data.get("confidence", 0.7))

        return DetectionResult(
            label=label,
            confidence=round(confidence, 3),
            is_low_confidence=confidence < (
                self.intent_threshold if task_type == "intent" else self.emotion_threshold
            ),
            method="llm",
        )