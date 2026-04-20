# API Reference

Base URL: `http://127.0.0.1:8000`

Interactive docs: `http://127.0.0.1:8000/api/docs`

---

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/health/ready` | Readiness check |
| POST | `/documents/upload` | Upload & ingest a document |
| GET | `/documents/{user_id}` | List user's documents |
| DELETE | `/documents/{user_id}/{document_id}` | Delete a document |
| POST | `/query` | RAG query with intent + emotion |
| POST | `/chat` | Multi-turn VoiceBot conversation |
| DELETE | `/chat/{session_id}` | Reset a session |
| GET | `/chat/{session_id}/context` | Inspect session state |
| POST | `/voice` | Voice input/output |

---

## Health

### GET /health

Liveness probe — confirms the server is running.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-03-15T10:30:00.000Z"
}
```

---

### GET /health/ready

Readiness probe — confirms dependencies are available.

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "vector_store": "ok",
    "openai_key_set": true
  },
  "timestamp": "2026-03-15T10:30:00.000Z"
}
```

---

## Documents

### POST /documents/upload

Upload and ingest a document. Extracts text, chunks it, generates embeddings, and stores in ChromaDB.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | File | ✅ | PDF, DOCX, TXT, MD, or CSV |
| user_id | string | ✅ | User identifier |
| document_id | string | ❌ | Custom ID, auto-generated if omitted |

**Example:**
```bash
curl -X POST http://127.0.0.1:8000/documents/upload \
  -F "file=@policy.pdf" \
  -F "user_id=user_123"
```

**Response:**
```json
{
  "document_id": "3f2a1b4c-9d8e-7f6a-5b4c-3d2e1f0a9b8c",
  "user_id": "user_123",
  "filename": "policy.pdf",
  "num_chunks": 14,
  "status": "success",
  "message": "Document ingested successfully into 14 chunks.",
  "created_at": "2026-03-15T10:30:00.000Z"
}
```

**Error Responses:**

| Code | Reason |
|------|--------|
| 400 | Unsupported file type |
| 413 | File too large (max 50MB) |
| 422 | Document is empty or unreadable |
| 500 | Ingestion failed |

---

### GET /documents/{user_id}

List all documents ingested by a user.

**Example:**
```bash
curl http://127.0.0.1:8000/documents/user_123
```

**Response:**
```json
{
  "user_id": "user_123",
  "documents": [
    {
      "document_id": "3f2a1b4c-...",
      "filename": "policy.pdf",
      "num_chunks": 14
    }
  ],
  "total": 1
}
```

---

### DELETE /documents/{user_id}/{document_id}

Remove a document and all its chunks from the vector store.

**Example:**
```bash
curl -X DELETE http://127.0.0.1:8000/documents/user_123/3f2a1b4c-...
```

**Response:**
```json
{
  "status": "deleted",
  "document_id": "3f2a1b4c-..."
}
```

---

## Query

### POST /query

Full RAG pipeline — detects intent and emotion, retrieves relevant chunks, generates a tone-aware answer.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | ✅ | User's question (max 2000 chars) |
| user_id | string | ✅ | User identifier |
| document_ids | array | ❌ | Filter to specific docs. null = all user docs |
| top_k | integer | ❌ | Number of chunks to retrieve (default: 5, max: 20) |

**Example:**
```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is your return policy?",
    "user_id": "user_123"
  }'
```

**Response:**
```json
{
  "query_id": "a1b2c3d4e5f6",
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
  "answer": "According to the return policy document: Returns are accepted within 7 days of delivery. Refunds are processed within 5 business days.",
  "retrieved_chunks": [
    {
      "chunk_id": "c1a2b3c4-...",
      "document_id": "3f2a1b4c-...",
      "filename": "policy.pdf",
      "content": "Returns are accepted within 7 days of delivery. Refunds are processed within 5 business days.",
      "score": 0.94,
      "page": 1
    }
  ],
  "fallback_triggered": false,
  "latency_ms": 312.5,
  "created_at": "2026-03-15T10:30:00.000Z"
}
```

---

## Chat (VoiceBot)

### POST /chat

Multi-turn conversation endpoint. Maintains session context, handles slot filling and context switching.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | ✅ | User's message (max 2000 chars) |
| user_id | string | ✅ | User identifier |
| session_id | string | ❌ | Omit to start a new session |

**Example:**
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "message": "Check my loan status"
  }'
```

**Response:**
```json
{
  "session_id": "fb82fd73-d411-416a-b388-0b7f3071ba61",
  "user_id": "user_123",
  "message": "I can help you check your loan status. Could you please provide your Loan ID?",
  "intent": "check_status",
  "emotion": "neutral",
  "slots": {},
  "turn_count": 1,
  "context_switched": false,
  "escalate_to_agent": false,
  "created_at": "2026-03-15T10:30:00.000Z"
}
```

---

### DELETE /chat/{session_id}

Reset and end a conversation session.

```bash
curl -X DELETE http://127.0.0.1:8000/chat/fb82fd73-...
```

**Response:**
```json
{
  "status": "deleted",
  "session_id": "fb82fd73-..."
}
```

---

### GET /chat/{session_id}/context

Inspect current session state — useful for debugging.

```bash
curl http://127.0.0.1:8000/chat/fb82fd73-.../context
```

**Response:**
```json
{
  "session_id": "fb82fd73-...",
  "user_id": "user_123",
  "current_intent": "check_status",
  "slots": {"loan_id": "12345"},
  "turn_count": 2,
  "history_length": 4
}
```

---

## Voice

### POST /voice

Voice-based interaction. Accepts audio (base64) or text fallback. Returns text reply and optional audio.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | ✅ | User identifier |
| audio_base64 | string | ❌ | Base64-encoded WAV/MP3 audio |
| text_fallback | string | ❌ | Plain text if no audio |
| session_id | string | ❌ | Existing session ID |

> At least one of `audio_base64` or `text_fallback` is required.

**Example (text fallback):**
```bash
curl -X POST http://127.0.0.1:8000/voice \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "text_fallback": "Check my loan status"
  }'
```

**Response:**
```json
{
  "session_id": "fb82fd73-...",
  "transcript": "Check my loan status",
  "reply_text": "Please provide your Loan ID.",
  "reply_audio_base64": "<base64-MP3-or-null>",
  "intent": "check_status",
  "emotion": "neutral",
  "turn_count": 1,
  "escalate_to_agent": false
}
```

---

## Response Fields Reference

### Intent values
`question` · `complaint` · `request` · `feedback` · `check_status` · `general_query` · `unknown`

### Emotion values
`happy` · `neutral` · `frustrated` · `angry`

### Response tone values
`formal` · `empathetic` · `apologetic` · `friendly` · `urgent`
