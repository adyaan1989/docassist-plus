import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config.settings import settings
from backend.models.schemas import ChatMessage, SessionContext
from backend.utils.logger import setup_logger

logger = setup_logger(__name__)


class InMemoryStore:
    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._expiry: Dict[str, float] = {}

    def get(self, key: str) -> Optional[str]:
        exp = self._expiry.get(key)
        if exp and time.time() > exp:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return None
        value = self._store.get(key)
        return json.dumps(value) if value is not None else None

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        self._store[key] = json.loads(value)
        self._expiry[key] = time.time() + ttl

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)


class SessionManager:
    def __init__(self):
        self._store = InMemoryStore()

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def _get_raw(self, session_id: str) -> Optional[str]:
        return self._store.get(self._key(session_id))

    async def _set_raw(self, session_id: str, data: str) -> None:
        self._store.set(self._key(session_id), data, settings.SESSION_TTL_SECONDS)

    async def _delete_raw(self, session_id: str) -> None:
        self._store.delete(self._key(session_id))

    async def create_session(self, user_id: str) -> SessionContext:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ctx = {"session_id": session_id, "user_id": user_id, "current_intent": None,
               "slots": {}, "history": [], "turn_count": 0, "created_at": now, "updated_at": now}
        await self._set_raw(session_id, json.dumps(ctx))
        return self._deserialize(ctx)

    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        raw = await self._get_raw(session_id)
        if not raw:
            return None
        return self._deserialize(json.loads(raw))

    async def get_or_create_session(self, user_id: str, session_id: Optional[str] = None) -> SessionContext:
        if session_id:
            session = await self.get_session(session_id)
            if session:
                return session
        return await self.create_session(user_id)

    async def update_session(self, session_id: str, user_message: str, assistant_reply: str,
                              intent: Optional[str] = None, new_slots: Optional[Dict[str, Any]] = None,
                              context_switched: bool = False) -> SessionContext:
        raw = await self._get_raw(session_id)
        if not raw:
            raise ValueError(f"Session {session_id} not found")
        ctx = json.loads(raw)
        if context_switched:
            ctx["slots"] = {}
            ctx["current_intent"] = intent
        elif intent:
            ctx["current_intent"] = intent
        if new_slots:
            ctx["slots"].update(new_slots)
        ctx["history"].append({"role": "user", "content": user_message})
        ctx["history"].append({"role": "assistant", "content": assistant_reply})
        if len(ctx["history"]) > 40:
            ctx["history"] = ctx["history"][-40:]
        ctx["turn_count"] += 1
        ctx["updated_at"] = datetime.utcnow().isoformat()
        await self._set_raw(session_id, json.dumps(ctx))
        return self._deserialize(ctx)

    async def delete_session(self, session_id: str) -> None:
        await self._delete_raw(session_id)

    def detect_context_switch(self, current_intent: Optional[str], new_intent: str, message: str) -> bool:
        if not current_intent or current_intent == new_intent:
            return False
        switch_phrases = ["actually", "instead", "forget that", "never mind", "cancel that", "i want to"]
        lower = message.lower()
        phrase_match = any(p in lower for p in switch_phrases)
        hard_switch_pairs = {("check_status", "complaint"), ("complaint", "check_status"), ("question", "complaint")}
        return phrase_match or (current_intent, new_intent) in hard_switch_pairs

    def extract_slots(self, message: str, intent: str) -> Dict[str, Any]:
        import re
        slots: Dict[str, Any] = {}
        patterns = {
            "loan_id": r"\b(?:loan|id|loan id)[:\s#]*([A-Z0-9]{4,12})\b",
            "order_id": r"\b(?:order|order id|order number)[:\s#]*([A-Z0-9\-]{4,15})\b",
            "complaint_id": r"\b(?:ticket|complaint|complaint id|ticket id)[:\s#]*(\d{4,10})\b",
        }
        for slot, pattern in patterns.items():
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                slots[slot] = m.group(1)
        if intent == "check_status" and "loan_id" not in slots:
            m = re.search(r"\b(\d{5,10})\b", message)
            if m:
                slots["loan_id"] = m.group(1)
        return slots

    def build_session_context_string(self, session: SessionContext) -> str:
        lines = [f"Intent: {session.current_intent or 'not set'}"]
        if session.slots:
            lines.append("Collected slots: " + ", ".join(f"{k}={v}" for k, v in session.slots.items()))
        else:
            lines.append("Collected slots: none yet")
        lines.append(f"Turn: {session.turn_count}")
        return " | ".join(lines)

    @staticmethod
    def _deserialize(ctx: dict) -> SessionContext:
        return SessionContext(
            session_id=ctx["session_id"], user_id=ctx["user_id"],
            current_intent=ctx.get("current_intent"), slots=ctx.get("slots", {}),
            history=[ChatMessage(role=m["role"], content=m["content"]) for m in ctx.get("history", [])],
            turn_count=ctx.get("turn_count", 0),
        )
