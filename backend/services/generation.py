"""
Response Generation Service
============================
Builds tone-aware prompts and calls the LLM to generate answers.

Design decisions:
- System prompt injects tone directives based on emotion/intent
- Retrieved chunks are provided as numbered context
- No hallucination guard: instructs model to say "I don't know" if context insufficient
- Structured output for consistent downstream parsing
"""

from typing import List, Optional
from openai import AsyncOpenAI

from backend.config.settings import settings
from backend.models.schemas import Emotion, Intent, ResponseTone
from backend.services.ingestion import SearchResult
from backend.utils.logger import setup_logger

logger = setup_logger(__name__)


# ── Tone directives ──────────────────────────────────────────────────────────

TONE_DIRECTIVES: dict[ResponseTone, str] = {
    ResponseTone.APOLOGETIC: (
        "The user is angry. Begin with a sincere apology. "
        "Acknowledge their frustration. Keep a calm, professional tone. "
        "Offer concrete next steps."
    ),
    ResponseTone.EMPATHETIC: (
        "The user is frustrated. Express empathy first. "
        "Validate their experience. Provide a clear, reassuring answer. "
        "Avoid dismissive language."
    ),
    ResponseTone.FRIENDLY: (
        "The user seems happy or positive. Respond warmly and enthusiastically. "
        "Keep it conversational and upbeat."
    ),
    ResponseTone.FORMAL: (
        "Respond professionally and directly. "
        "Be precise and complete. Avoid unnecessary padding."
    ),
    ResponseTone.URGENT: (
        "The user needs an urgent resolution. Be concise and action-oriented. "
        "Provide immediate next steps."
    ),
}

BASE_SYSTEM_PROMPT = """You are DocAssist+, a helpful AI assistant for customer support.

CONTEXT USAGE RULES:
- Answer ONLY using the provided document context.
- If the context does not contain enough information, say: "I'm sorry, I don't have enough information to answer that accurately. Please contact support for more details."
- Never fabricate facts, policies, or numbers.
- Cite which part of the context supports your answer (e.g., "According to the return policy...").

TONE DIRECTIVE:
{tone_directive}

FORMAT:
- Keep answers concise (2-4 sentences unless more detail is needed).
- Use bullet points for lists or steps.
- Do not repeat the question back to the user."""

CHAT_SYSTEM_PROMPT = """You are a helpful customer support assistant (VoiceBot).

CAPABILITIES:
- Check order/loan/complaint status
- Register new complaints
- Answer general queries
- Maintain conversation context across turns

SLOT TRACKING:
- When you need a piece of information (loan_id, order_id, etc.), explicitly ask for it.
- When you receive it, confirm and proceed.
- If the user changes topic, gracefully acknowledge the switch.

CONTEXT CONTINUITY:
- The conversation history below maintains all context.
- Reference prior turns naturally (e.g., "As I mentioned earlier...").

ESCALATION:
- If the user is very angry, or the issue cannot be resolved, say:
  "I'm escalating this to a human agent now. Please hold."

FALLBACK:
- If you cannot help: "I'm sorry, I'm unable to assist with that. Shall I connect you to a human agent?"

{tone_directive}

CURRENT SESSION CONTEXT:
{session_context}"""


class ResponseGenerator:
    """Generates LLM responses for RAG queries."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_rag_answer(
        self,
        query: str,
        chunks: List[SearchResult],
        intent: Intent,
        emotion: Emotion,
        tone: ResponseTone,
        session_id: Optional[str] = None,
    ) -> tuple[str, bool]:
        """
        Returns (answer_text, fallback_triggered).
        fallback_triggered=True when context was insufficient.
        """
        tone_directive = TONE_DIRECTIVES.get(tone, TONE_DIRECTIVES[ResponseTone.FORMAL])
        system = BASE_SYSTEM_PROMPT.format(tone_directive=tone_directive)

        # Build numbered context block
        if chunks:
            context_block = "\n\n".join(
                f"[{i+1}] (Source: {c.filename}, score={c.score:.2f})\n{c.content}"
                for i, c in enumerate(chunks)
            )
        else:
            context_block = "No relevant context found."

        user_message = f"""DOCUMENT CONTEXT:
{context_block}

USER QUERY:
{query}

Please answer the query using only the context above."""

        try:
            response = await self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            answer = response.choices[0].message.content.strip()
            fallback = "don't have enough information" in answer.lower() or not chunks
            return answer, fallback

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return (
                "I'm sorry, I'm experiencing technical difficulties. "
                "Please try again shortly or contact support.",
                True,
            )


class ChatResponseGenerator:
    """Generates multi-turn conversational responses for the VoiceBot."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_chat_response(
        self,
        history: list,          # list of {"role": ..., "content": ...}
        session_context: str,
        tone: ResponseTone,
        current_intent: Optional[str] = None,
    ) -> tuple[str, bool]:
        """
        Returns (reply_text, escalate_to_agent).
        """
        tone_directive = TONE_DIRECTIVES.get(tone, TONE_DIRECTIVES[ResponseTone.FORMAL])
        system = CHAT_SYSTEM_PROMPT.format(
            tone_directive=tone_directive,
            session_context=session_context,
        )

        messages = [{"role": "system", "content": system}] + history

        try:
            response = await self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            reply = response.choices[0].message.content.strip()
            escalate = "escalating" in reply.lower() or "human agent" in reply.lower()
            return reply, escalate

        except Exception as e:
            logger.error(f"Chat LLM generation failed: {e}")
            return (
                "I'm sorry, I'm having trouble responding right now. "
                "Please try again or call our support line.",
                False,
            )