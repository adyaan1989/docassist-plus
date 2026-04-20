# DocAssist+ & VoiceBot

> Production-grade AI assistant that answers questions from documents, detects user intent & emotion, and runs a multi-turn customer support VoiceBot.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-orange)
![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-purple)

---

## What It Does

| Feature | Description |
|---------|-------------|
| 📄 Document Q&A | Upload PDFs/DOCX and ask questions — answers grounded in your documents |
| 🎯 Intent Detection | Classifies user intent: question, complaint, request, check_status, feedback |
| 😊 Emotion Detection | Detects emotion: happy, neutral, frustrated, angry |
| 🎨 Tone Adjustment | Response tone changes based on intent × emotion (apologetic, empathetic, formal, friendly) |
| 🎙️ VoiceBot | Multi-turn conversations with slot filling and context switching |
| 🔊 Voice I/O | Optional STT (Whisper) and TTS support |

---

## Quick Start

```bash
# 1. Clone and setup
git clone <your-repo-url>
cd docassist-plus
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run
uvicorn backend.main:app --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- **API:** http://127.0.0.1:8000
- **API Docs:** http://127.0.0.1:8000/api/docs
- **Frontend:** http://localhost:5173

---

## Project Structure

```
docassist-plus/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── config/settings.py      # All configuration via .env
│   ├── models/schemas.py       # Request/response data models
│   ├── routers/                # API endpoints
│   │   ├── documents.py        # Upload, list, delete documents
│   │   ├── query.py            # RAG query pipeline
│   │   ├── chat.py             # Multi-turn VoiceBot
│   │   ├── voice.py            # STT → chat → TTS
│   │   └── health.py           # Health checks
│   └── services/               # Core business logic
│       ├── ingestion.py        # Extract → Chunk → Embed → Store
│       ├── detection.py        # Intent + emotion detection
│       ├── generation.py       # LLM response generation
│       └── session.py          # Session & context management
├── frontend/
│   └── src/App.jsx             # React UI
├── tests/
│   └── test_services.py        # Unit & integration tests
├── docs/                       # Project documentation
├── .env.example                # Environment variable template
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, components, data flow |
| [API Reference](docs/API.md) | All endpoints with request/response examples |
| [Sample I/O](docs/SAMPLE_IO.md) | Real examples of all 3 VoiceBot scenarios |
| [Setup Guide](docs/SETUP.md) | Detailed installation and configuration |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | text-embedding-3-small |
| Vector Store | ChromaDB |
| Session Store | Redis (in-memory fallback) |
| PDF Parsing | PyMuPDF |
| Frontend | React + Vite + Tailwind |
| STT | OpenAI Whisper-1 |
| TTS | OpenAI TTS-1 |

---

## Running Tests

```bash
pytest tests/ -v
```
