# Architecture

## System Overview

DocAssist+ is built as a modular FastAPI backend with two main pipelines — a RAG (Retrieval-Augmented Generation) pipeline for document Q&A, and a VoiceBot pipeline for multi-turn conversations.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                        │
│           React UI  /  REST API  /  Voice (STT/TTS)     │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI GATEWAY                        │
│        CORS · GZip · Rate Limit · Request Tracing       │
│                                                          │
│   /documents    /query    /chat    /voice    /health     │
└──────┬───────────────┬──────────────┬───────────────────┘
       │               │              │
┌──────▼──────┐  ┌─────▼──────────────▼──────────────────┐
│  INGESTION  │  │           CORE SERVICES                 │
│  PIPELINE   │  │                                         │
│             │  │  Intent Detector   Emotion Detector     │
│  Extract    │  │  (rule + LLM)      (rule + LLM)        │
│  ↓          │  │        ↓                 ↓              │
│  Chunk      │  │   Tone Matrix      Session Manager      │
│  ↓          │  │        ↓                 ↓              │
│  Embed      │  │  LLM Generator     Slot Extractor       │
│  ↓          │  │  (GPT-4o-mini)     Context Switch       │
│  ChromaDB   │  │                                         │
└─────────────┘  └─────────────────────────────────────────┘
       │                        │
┌──────▼────────────────────────▼──────┐
│           DATA LAYER                  │
│   ChromaDB (vectors)                  │
│   Redis (sessions, TTL 1hr)           │
│   In-memory fallback (dev)            │
└───────────────────────────────────────┘
```

---

## Components

### 1. Document Ingestion Pipeline

Handles converting raw files into searchable vector embeddings.

```
File Upload
    ↓
Text Extractor
  - PDF  → PyMuPDF (fallback: pdfplumber)
  - DOCX → python-docx
  - TXT/MD/CSV → direct decode
    ↓
Recursive Chunker
  - Chunk size: 512 characters
  - Overlap: 64 characters
  - Strategy: paragraphs → sentences → words
    ↓
Embedding Service
  - Model: text-embedding-3-small
  - Batch size: 100 chunks per API call
    ↓
ChromaDB Vector Store
  - One collection per user (data isolation)
  - Cosine similarity search
  - Persistent to disk
```

**Why 512 chars with 64 overlap?**
Large enough to contain a complete thought, small enough for precise retrieval. Overlap ensures answers that span two chunks aren't lost.

---

### 2. RAG Query Pipeline

```
User Query
    ↓
Intent + Emotion Detection (hybrid)
  - Rule-based regex first (0ms, free)
  - LLM fallback if confidence < 0.6
    ↓
Query Embedding
  - Same model as ingestion (text-embedding-3-small)
    ↓
Vector Search
  - Top-K = 5 chunks (configurable)
  - Filtered by user_id and optional document_ids
    ↓
Tone Selection
  - Intent × Emotion → Tone matrix
  - complaint + angry   → apologetic
  - complaint + frustrated → empathetic
  - question + neutral  → formal
  - question + happy    → friendly
    ↓
LLM Generation
  - System prompt includes tone directive
  - Context = numbered chunks with source labels
  - Instruction: answer only from context, say "I don't know" if insufficient
    ↓
Response with metadata
  - answer, intent, emotion, tone, chunks, latency
```

---

### 3. VoiceBot Pipeline

```
User Message (text or audio)
    ↓
STT (if audio) → OpenAI Whisper-1
    ↓
Session Lookup (Redis / in-memory)
  - Create new session if none exists
    ↓
Intent + Emotion Detection
    ↓
Context Switch Detection
  - Checks for phrases: "actually", "instead", "never mind"
  - Checks for hard intent pairs: check_status ↔ complaint
  - If switch: clears slots, resets intent
    ↓
Slot Extraction (regex)
  - loan_id, order_id, complaint_id
    ↓
LLM Generation
  - Full conversation history in prompt (last 20 turns)
  - Session context injected into system prompt
    ↓
Session Update
  - Append turn to history
  - Update slots and intent
  - Reset TTL in Redis
    ↓
TTS (optional) → OpenAI TTS-1 (nova voice)
    ↓
Response with session state
```

---

## Intent × Emotion → Tone Matrix

| Intent | Emotion | Tone |
|--------|---------|------|
| complaint | angry | apologetic |
| complaint | frustrated | empathetic |
| complaint | neutral | formal |
| question | happy | friendly |
| question | neutral | formal |
| check_status | frustrated | empathetic |
| check_status | neutral | formal |
| request | neutral | formal |
| feedback | happy | friendly |
| *(default)* | *(any)* | formal |

---

## Hybrid Detection Strategy

```
Message
  ↓
Rule-based classifier
  - Regex patterns for each intent/emotion
  - Returns confidence score
  ↓
confidence >= threshold?
  ├── YES → use rule result (fast, free)
  └── NO  → call LLM classifier
              - GPT-4o-mini with JSON response format
              - Returns label + confidence
              - Runs in parallel for intent and emotion
```

**Why hybrid?**
~80% of messages are obvious (contain "what", "?", "ridiculous", "thank you") and can be classified by rules in 0ms at zero cost. Only edge cases need the LLM.

---

## Session Management

```
Session stored as JSON in Redis:
{
  "session_id": "uuid",
  "user_id": "user_123",
  "current_intent": "check_status",
  "slots": {"loan_id": "12345"},
  "history": [
    {"role": "user", "content": "Check my loan"},
    {"role": "assistant", "content": "Please provide loan ID"}
  ],
  "turn_count": 2,
  "updated_at": "2026-03-15T10:30:00Z"
}
```

- TTL: 1 hour of inactivity
- History capped at 40 messages (20 turns) to control token usage
- Falls back to in-memory store if Redis unavailable

---

## Key Design Decisions

### Why GPT-4o-mini?
15× cheaper than GPT-4, handles document Q&A and conversation well. Easy to upgrade to GPT-4o by changing one env variable.

### Why ChromaDB?
Zero infrastructure needed for development. Persistent to disk. Can be swapped to Pinecone or Qdrant by implementing the same interface — `VECTOR_STORE_TYPE` env var controls this.

### Why top-K = 5?
At ~512 chars/chunk, 5 chunks ≈ 2,500 chars of context. Fits well within GPT-4o-mini's window while keeping prompts lean and costs low.

### Why stateless API?
All state lives in Redis (sessions) and ChromaDB (vectors). This means the API workers are fully stateless — you can run 10 workers behind a load balancer and any worker can handle any request.

---

## Production Scaling

```
Load Balancer
  ├── API Worker 1  ─┐
  ├── API Worker 2  ─┤── Redis (shared sessions)
  ├── API Worker 3  ─┤── ChromaDB / Pinecone (shared vectors)
  └── API Worker N  ─┘
```

- **Horizontal scaling:** add more API workers, no code changes needed
- **Cost control:** Redis cache for repeated queries (5min TTL)
- **Rate limiting:** 60 req/min per user
- **Latency:** rule-based detection adds 0ms, LLM fallback ~200ms
