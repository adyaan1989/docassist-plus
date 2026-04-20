# Setup Guide

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | any | `git --version` |

You also need an **OpenAI API key** from https://platform.openai.com/api-keys

Redis is optional — the app falls back to in-memory sessions automatically.

---

## Installation

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd docassist-plus
```

### 2. Create Python virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
nano .env   # or open in any editor
```

Set your OpenAI API key:
```env
OPENAI_API_KEY=sk-proj-your-real-key-here
```

Everything else has sensible defaults and works as-is for development.

### 5. Start the backend

```bash
uvicorn backend.main:app --port 8000
```

You should see:
```
🚀 DocAssist+ API starting up...
   Environment : development
   LLM Model   : gpt-4o-mini
   Embed Model : text-embedding-3-small
Uvicorn running on http://127.0.0.1:8000
```

### 6. Set up the frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

---

## Verify Everything Works

```bash
# Health check
curl http://127.0.0.1:8000/health

# Expected:
# {"status":"ok","timestamp":"..."}
```

Open the API docs in your browser:
```
http://127.0.0.1:8000/api/docs
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `LLM_MODEL` | `gpt-4o-mini` | LLM for generation and fallback detection |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model for vector embeddings |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (falls back to memory if unavailable) |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Where ChromaDB stores vectors on disk |
| `CHUNK_SIZE` | `512` | Characters per document chunk |
| `CHUNK_OVERLAP` | `64` | Overlapping characters between chunks |
| `TOP_K` | `5` | Number of chunks to retrieve per query |
| `SESSION_TTL_SECONDS` | `3600` | Session expiry time (1 hour) |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |

---

## Running with Docker

Requires Docker and Docker Compose.

```bash
cp .env.example .env
# Add your OPENAI_API_KEY to .env

docker compose up
```

This starts:
- API on http://localhost:8000
- Redis on localhost:6379
- Frontend on http://localhost:3000

---

## Running Tests

```bash
# Make sure venv is active
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=backend --cov-report=html
# Open htmlcov/index.html to view coverage
```

---

## Common Issues

### Port 8000 already in use
```bash
# Find and kill the process
sudo fuser -k 8000/tcp
# Then restart
uvicorn backend.main:app --port 8000
```

### ChromaDB telemetry warnings
```
Failed to send telemetry event: capture() takes 1 positional argument
```
This is a harmless ChromaDB bug — ignore it. Does not affect functionality.

### OpenAI 401 error
Your API key is wrong or still set to the placeholder. Check your `.env`:
```bash
cat .env | grep OPENAI
# Should show your real key, not sk-your-openai-api-key-here
```

### Module not found errors
Make sure your virtual environment is activated:
```bash
source .venv/bin/activate
which python   # should point to .venv/bin/python
```

### Frontend can't reach backend
The frontend calls `http://127.0.0.1:8000`. Make sure:
1. Backend is running on port 8000
2. CORS is configured — check `ALLOWED_ORIGINS` in `.env`
