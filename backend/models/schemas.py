from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import uuid
from datetime import datetime


class Intent(str, Enum):
    QUESTION = "question"
    COMPLAINT = "complaint"
    REQUEST = "request"
    FEEDBACK = "feedback"
    CHECK_STATUS = "check_status"
    GENERAL_QUERY = "general_query"
    UNKNOWN = "unknown"


class Emotion(str, Enum):
    HAPPY = "happy"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"


class ResponseTone(str, Enum):
    FORMAL = "formal"
    EMPATHETIC = "empathetic"
    APOLOGETIC = "apologetic"
    FRIENDLY = "friendly"
    URGENT = "urgent"


class DocumentUploadResponse(BaseModel):
    document_id: str
    user_id: str
    filename: str
    num_chunks: int
    status: str
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    num_chunks: int


class DocumentListResponse(BaseModel):
    user_id: str
    documents: List[Any]
    total: int


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    user_id: str
    document_ids: Optional[List[str]] = None
    top_k: Optional[int] = Field(5, ge=1, le=20)
    session_id: Optional[str] = None

    @validator("query")
    def clean_query(cls, v):
        return v.strip()


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    content: str
    score: float
    page: Optional[int] = None


class IntentResult(BaseModel):
    intent: Intent
    confidence: float
    is_low_confidence: bool


class EmotionResult(BaseModel):
    emotion: Emotion
    confidence: float
    is_low_confidence: bool


class QueryResponse(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    query: str
    intent: IntentResult
    emotion: EmotionResult
    response_tone: ResponseTone
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    fallback_triggered: bool = False
    latency_ms: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    message: str = Field(..., min_length=1, max_length=2000)

    @validator("message")
    def clean_message(cls, v):
        return v.strip()


class SessionContext(BaseModel):
    session_id: str
    user_id: str
    current_intent: Optional[str] = None
    slots: Dict[str, Any] = Field(default_factory=dict)
    history: List[ChatMessage] = Field(default_factory=list)
    turn_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatResponse(BaseModel):
    session_id: str
    user_id: str
    message: str
    intent: Optional[Intent] = None
    emotion: Optional[Emotion] = None
    slots: Dict[str, Any] = Field(default_factory=dict)
    turn_count: int
    context_switched: bool = False
    escalate_to_agent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    audio_base64: Optional[str] = None
    text_fallback: Optional[str] = None


class VoiceResponse(BaseModel):
    session_id: str
    transcript: str
    reply_text: str
    reply_audio_base64: Optional[str] = None
    intent: Optional[Intent] = None
    emotion: Optional[Emotion] = None
    turn_count: int
    escalate_to_agent: bool = False
