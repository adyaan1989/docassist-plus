"""
Voice Router
============
POST /voice  — Voice input (STT → intent → response → TTS)
             — Can mock STT/TTS in dev; integrates OpenAI Whisper + TTS
"""

import base64
import io
from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    Emotion, Intent, VoiceRequest, VoiceResponse,
)
from backend.routers.chat import _detector, _generator, _session_mgr
from backend.utils.logger import setup_logger
from backend.config.settings import settings
from openai import AsyncOpenAI

router = APIRouter()
logger = setup_logger(__name__)
_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def transcribe_audio(audio_base64: str) -> str:
    """Convert base64 audio to text using OpenAI Whisper."""
    try:
        audio_bytes = base64.b64decode(audio_base64)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        transcript = await _client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcript.text
    except Exception as e:
        logger.error(f"STT failed: {e}")
        raise HTTPException(status_code=422, detail=f"Speech transcription failed: {e}")


async def synthesize_speech(text: str) -> str:
    """Convert text to speech using OpenAI TTS. Returns base64 audio."""
    try:
        response = await _client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            response_format="mp3",
        )
        audio_bytes = response.content
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"TTS failed (non-critical): {e}")
        return ""


@router.post("", response_model=VoiceResponse)
async def voice_interaction(req: VoiceRequest):
    """
    Voice-based customer support interaction.

    Input modes:
    - audio_base64: raw audio (WAV/MP3) → Whisper STT
    - text_fallback: plain text (used when audio unavailable)

    Output:
    - reply_text: assistant response
    - reply_audio_base64: TTS audio (omitted if TTS fails)
    - intent, emotion, session state
    """
    if not req.audio_base64 and not req.text_fallback:
        raise HTTPException(
            status_code=400,
            detail="Provide either audio_base64 or text_fallback"
        )

    # 1. STT or text fallback
    if req.audio_base64:
        transcript = await transcribe_audio(req.audio_base64)
        logger.info(f"STT transcript: '{transcript[:80]}...' ")
    else:
        transcript = req.text_fallback

    # 2. Get/create session
    session = await _session_mgr.get_or_create_session(req.user_id, req.session_id)

    # 3. Detect intent + emotion
    intent_result, emotion_result = await _detector.detect(transcript)
    intent_enum = Intent(intent_result.label)
    emotion_enum = Emotion(emotion_result.label)
    tone = _detector.get_response_tone(intent_enum, emotion_enum)

    # 4. Context switch + slots
    context_switched = _session_mgr.detect_context_switch(
        session.current_intent, intent_result.label, transcript
    )
    new_slots = _session_mgr.extract_slots(transcript, intent_result.label)
    session.slots = {**session.slots, **new_slots}
    session_context_str = _session_mgr.build_session_context_string(session)

    # 5. Generate text reply
    history = [{"role": m.role, "content": m.content} for m in session.history[-20:]]
    history.append({"role": "user", "content": transcript})
    reply_text, escalate = await _generator.generate_chat_response(
        history=history,
        session_context=session_context_str,
        tone=tone,
    )

    # 6. TTS (optional, non-blocking failure)
    reply_audio = await synthesize_speech(reply_text)

    # 7. Persist session
    updated = await _session_mgr.update_session(
        session_id=session.session_id,
        user_message=transcript,
        assistant_reply=reply_text,
        intent=intent_result.label,
        new_slots=new_slots,
        context_switched=context_switched,
    )

    return VoiceResponse(
        session_id=session.session_id,
        transcript=transcript,
        reply_text=reply_text,
        reply_audio_base64=reply_audio or None,
        intent=intent_enum,
        emotion=emotion_enum,
        turn_count=updated.turn_count,
        escalate_to_agent=escalate,
    )