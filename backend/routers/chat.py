"""
Chat Router — Multi-turn VoiceBot
===================================
POST /chat        → text conversation
DELETE /chat/{session_id} → reset session
GET  /chat/{session_id}/context → inspect session state
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ChatRequest, ChatResponse, Emotion, Intent, ResponseTone
from backend.services.detection import IntentEmotionDetector
from backend.services.generation import ChatResponseGenerator
from backend.services.session import SessionManager
from backend.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)

_detector = IntentEmotionDetector()
_generator = ChatResponseGenerator()
_session_mgr = SessionManager()


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Multi-turn text conversation endpoint.

    Handles:
    - Slot filling (loan_id, order_id, complaint_id)
    - Context switching between intents
    - Emotion-aware tone adjustment
    - Escalation to human agent

    **Scenario 1 — Slot Filling:**
    ```
    User: "Check my loan status"
    Bot:  "Please provide your Loan ID"
    User: "12345"
    Bot:  "Your loan #12345 is currently approved."
    ```

    **Scenario 2 — Context Continuity:**
    ```
    User: "I want to raise a complaint"
    Bot:  "Please describe your issue"
    User: "Payment failed"
    Bot:  "Complaint registered (Ticket ID: TKT-5678)"
    User: "What is the status?"
    Bot:  "Your complaint (Ticket TKT-5678) is in progress."
    ```

    **Scenario 3 — Context Switch:**
    ```
    User: "Check my loan status"
    Bot:  "Please provide your Loan ID"
    User: "Actually I want to raise complaint"
    Bot:  "Sure, please describe your issue"
    ```
    """
    # 1. Get or create session
    session = await _session_mgr.get_or_create_session(req.user_id, req.session_id)

    # 2. Detect intent + emotion
    intent_result, emotion_result = await _detector.detect(req.message)
    new_intent = intent_result.label
    intent_enum = Intent(new_intent)
    emotion_enum = Emotion(emotion_result.label)
    tone = _detector.get_response_tone(intent_enum, emotion_enum)

    # 3. Detect context switch
    context_switched = _session_mgr.detect_context_switch(
        current_intent=session.current_intent,
        new_intent=new_intent,
        message=req.message,
    )

    # 4. Extract slots from this message
    new_slots = _session_mgr.extract_slots(req.message, new_intent)

    # 5. Build conversation history for LLM (OpenAI format)
    history = [
        {"role": m.role, "content": m.content}
        for m in session.history[-20:]  # last 10 turns
    ]
    history.append({"role": "user", "content": req.message})

    # 6. Build session context string for prompt injection
    # Merge new slots with existing
    merged_slots = {**session.slots, **new_slots}
    session.slots = merged_slots
    session.current_intent = intent_enum.value if context_switched else (session.current_intent or intent_enum.value)
    session_context_str = _session_mgr.build_session_context_string(session)

    # 7. Generate reply
    reply, escalate = await _generator.generate_chat_response(
        history=history,
        session_context=session_context_str,
        tone=tone,
        current_intent=session.current_intent,
    )

    # 8. Persist updated session
    updated_session = await _session_mgr.update_session(
        session_id=session.session_id,
        user_message=req.message,
        assistant_reply=reply,
        intent=new_intent,
        new_slots=new_slots,
        context_switched=context_switched,
    )

    logger.info(
        f"[{session.session_id}] Turn {updated_session.turn_count} | "
        f"intent={new_intent} emotion={emotion_enum.value} "
        f"switch={context_switched} escalate={escalate}"
    )

    return ChatResponse(
        session_id=session.session_id,
        user_id=req.user_id,
        message=reply,
        intent=intent_enum,
        emotion=emotion_enum,
        slots=updated_session.slots,
        turn_count=updated_session.turn_count,
        context_switched=context_switched,
        escalate_to_agent=escalate,
    )


@router.delete("/{session_id}")
async def reset_session(session_id: str):
    """Reset / end a conversation session."""
    await _session_mgr.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.get("/{session_id}/context")
async def get_session_context(session_id: str):
    """Inspect the current session context (for debugging)."""
    session = await _session_mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "current_intent": session.current_intent,
        "slots": session.slots,
        "turn_count": session.turn_count,
        "history_length": len(session.history),
    }