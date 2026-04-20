# DocAssist+ & VoiceBot — Production Implementation

> Full end-to-end implementation of the DocAssist+ RAG system and VoiceBot customer support agent.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                               │
│        React UI (DocAssist tab + VoiceBot tab)                     │
│        REST API · Optional Voice (STT/TTS via Whisper)             │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼─────────────────────────────────────────┐
│                     FastAPI GATEWAY                                 │
│   CORS · GZip · Rate Limit · Request-ID · Global Error Handler     │
│                                                                     │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ /documents  │  │  /query  │  │  /chat   │  │    /voice      │  │
│  └──────┬──────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │
└─────────┼──────────────┼─────────────┼────────────────┼───────────┘
          │              │             │                │
┌─────────▼──────┐  ┌────▼──────────────────────────────▼──────────┐
│  INGESTION     │  │            CORE SERVICES                      │
│  PIPELINE      │  │                                               │
│                │  │  Intent Detector    Emotion Detector          │
│  Extract text  │  │  (rule + LLM)       (rule + LLM)             │
│  ↓             │  │       ↓                   ↓                   │
│  Chunk (512+64)│  │  Response Tone      Session Manager           │
│  ↓             │  │  (tone matrix)      (Redis / in-memory)       │
│  Embed         │  │       ↓                   ↓                   │
│  (ada-3-small) │  │  LLM Generator      Context Switch            │
│  ↓             │  │  (GPT-4o-mini)      Slot Filling              │
│  ChromaDB      │  │                                               │
└────────────────┘  └───────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ ChromaDB    │
                    │ (vector)    │
                    │ Redis       │
                    │ (sessions)  │
                    └─────────────┘
```

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone <repo>
cd docassist-plus
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY
docker compose up
```

- API:      http://localhost:8000/api/docs
- Frontend: http://localhost:3000

### Option 2: Local Development

```bash
# Backend
uv venv
source .venv/bin/activate

pip install -r requirements.txt
uv pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
python main.py
uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm create vite@5 . -- --template react
npm install
npm run dev
```

---

## Environment Variables

```env
OPENAI_API_KEY=sk-...          # Required
LLM_MODEL=gpt-4o-mini          # Cost-optimised default
EMBEDDING_MODEL=text-embedding-3-small
ENVIRONMENT=development
REDIS_URL=redis://localhost:6379
CHROMA_PERSIST_DIR=./chroma_db
CHUNK_SIZE=512
CHUNK_OVERLAP=64
TOP_K=5
SESSION_TTL_SECONDS=3600
```

---

## API Reference

### POST /documents/upload

Upload and ingest a document.

**Request** (multipart/form-data):
```
file:        <binary — PDF/DOCX/TXT/MD/CSV>
user_id:     "user_123"
document_id: "doc_abc"   # optional
```

**Response:**
```json
{
  "document_id": "3f2a1b4c-...",
  "user_id": "user_123",
  "filename": "policy.pdf",
  "num_chunks": 14,
  "status": "success",
  "message": "Document ingested successfully into 14 chunks.",
  "created_at": "2026-03-15T10:30:00Z"
}
```

---

### POST /query

Full RAG pipeline with intent + emotion detection.

**Request:**
```json
{
  "query": "What is your return policy?",
  "user_id": "user_123",
  "document_ids": null,
  "top_k": 5
}
```

**Response:**
```json
{
  "query_id": "a1b2c3d4",
  "query": "What is your return policy?",
  "intent": {
    "intent": "question",
    "confidence": 0.91,
    "is_low_confidence": false
  },
  "emotion": {
    "emotion": "neutral",
    "confidence": 0.85,
    "is_low_confidence": false
  },
  "response_tone": "formal",
  "answer": "According to the return policy: Returns are accepted within 7 days of delivery. Refunds are processed within 5 business days.",
  "retrieved_chunks": [
    {
      "chunk_id": "c1a2b3c4-...",
      "document_id": "3f2a1b4c-...",
      "filename": "policy.pdf",
      "content": "Returns are accepted within 7 days of delivery...",
      "score": 0.94,
      "page": 1
    }
  ],
  "fallback_triggered": false,
  "latency_ms": 312.5,
  "created_at": "2026-03-15T10:30:01Z"
}
```

---

### POST /chat

Multi-turn VoiceBot conversation.

**Request:**
```json
{
  "session_id": null,
  "user_id": "user_123",
  "message": "Check my loan status"
}
```

**Response:**
```json
{
  "session_id": "sess_7a8b9c",
  "user_id": "user_123",
  "message": "I can help you check your loan status. Could you please provide your Loan ID?",
  "intent": "check_status",
  "emotion": "neutral",
  "slots": {},
  "turn_count": 1,
  "context_switched": false,
  "escalate_to_agent": false
}
```

---

### POST /voice

Voice input/output endpoint.

**Request:**
```json
{
  "session_id": "sess_7a8b9c",
  "user_id": "user_123",
  "audio_base64": "<base64-WAV>",
  "text_fallback": "Check my loan status"
}
```

**Response:**
```json
{
  "session_id": "sess_7a8b9c",
  "transcript": "Check my loan status",
  "reply_text": "Please provide your Loan ID.",
  "reply_audio_base64": "<base64-MP3>",
  "intent": "check_status",
  "emotion": "neutral",
  "turn_count": 1,
  "escalate_to_agent": false
}
```

---

## Multi-Turn Scenarios

### Scenario 1: Slot Filling
```
→ POST /chat  {"message": "Check my loan status"}
← "Please provide your Loan ID."

→ POST /chat  {"message": "12345", "session_id": "sess_..."}
← "Your loan #12345 is currently Approved."
   slots: {"loan_id": "12345"}
```

### Scenario 2: Context Continuity
```
→ "I want to raise a complaint"
← "Please describe your issue."

→ "Payment failed"
← "Complaint registered (Ticket ID: TKT-5678)."
   slots: {"complaint_id": "TKT-5678"}

→ "What is the status?"
← "Your complaint (Ticket TKT-5678) is In Progress."
```

### Scenario 3: Context Switch
```
→ "Check my loan status"
← "Please provide your Loan ID."

→ "Actually I want to raise complaint"    ← "actually" triggers switch
← "Sure, please describe your issue."
   context_switched: true
   slots: {}  (cleared)
```

---

## Key Design Decisions

### Embedding: text-embedding-3-small
- 5× cheaper than ada-002, comparable quality
- 1536 dimensions with Matryoshka — can truncate for speed
- Cosine similarity in ChromaDB (normalized, range-stable)

### Top-K = 5
- Balances context quality vs prompt token cost
- At ~512 tokens/chunk, 5 chunks = ~2560 tokens → fits gpt-4o-mini 128k window
- Configurable via `TOP_K` env var

### When to use LLM vs not
| Decision | Method |
|----------|--------|
| Intent detection (high confidence) | Rule-based regex — 0ms, $0 |
| Intent detection (low confidence) | LLM with JSON response — ~200ms |
| Emotion detection | Same hybrid pattern |
| RAG answer generation | Always LLM (with context) |
| Slot extraction | Regex — instant |
| Context switch detection | Phrase + intent delta — instant |

### Chunking Strategy
- Recursive splitter: paragraphs → sentences → words
- 512 tokens / 64 token overlap
- Overlap prevents answer from straddling chunk boundary

---

## Production Considerations

### Multi-user Support
- Per-user ChromaDB collection (data isolation)
- Session keyed by `session_id` in Redis
- Stateless API workers — horizontally scalable

### Latency Reduction
- Rule-based detection first (0ms) — LLM only on fallback
- Embedding cache (Redis) for repeated queries
- Async throughout — no blocking I/O
- GZip middleware for response compression

### Cost Reduction
- `gpt-4o-mini` instead of GPT-4 — 15× cheaper
- `text-embedding-3-small` — 5× cheaper than ada-002
- Response cache (Redis, 5min TTL) for identical queries
- Sliding window history (last 20 turns) — caps token usage

### Edge Case Handling
| Edge Case | Handling |
|-----------|----------|
| Wrong chunks retrieved | Answer states "not enough info" — fallback_triggered=true |
| Low-confidence intent | LLM classifier fallback; response notes uncertainty |
| Slow LLM response | 30s timeout; graceful error message returned |
| Missing session | Auto-creates new session |
| Context switch mid-flow | Slots cleared, intent reset |
| Escalation needed | escalate_to_agent=true in response |

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=backend --cov-report=html
```

---

## Tools & LLMs Used

| Component | Tool |
|-----------|------|
| API Framework | FastAPI 0.111 |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | text-embedding-3-small |
| Vector Store | ChromaDB (local, persistent) |
| Session Store | Redis (in-memory fallback) |
| PDF Parsing | PyMuPDF |
| DOCX Parsing | python-docx |
| STT | OpenAI Whisper-1 |
| TTS | OpenAI TTS-1 (nova voice) |
| Frontend | React + Tailwind |

---

## Folder Structure

```
docassist-plus/
├── backend/
│   ├── main.py               # FastAPI app + middleware
│   ├── config/settings.py    # Pydantic settings
│   ├── models/schemas.py     # All request/response models
│   ├── routers/
│   │   ├── documents.py      # Upload / list / delete
│   │   ├── query.py          # RAG query pipeline
│   │   ├── chat.py           # Multi-turn VoiceBot
│   │   ├── voice.py          # STT → chat → TTS
│   │   └── health.py         # Liveness + readiness
│   ├── services/
│   │   ├── ingestion.py      # Extract → chunk → embed → store
│   │   ├── detection.py      # Intent + emotion (hybrid)
│   │   ├── generation.py     # LLM response generation
│   │   └── session.py        # Session + slot + context switch
│   └── utils/logger.py
├── frontend/
│   └── App.jsx               # React UI (DocAssist + VoiceBot)
├── tests/
│   └── test_services.py      # Unit + integration tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

SECRET_KEY:
need to create using below commond and the key need to update into .env
python -c "import secrets; print(secrets.token_hex(32))"