# PGAGI Candidate Screening System

A role-based candidate screening system with a slim React frontend and a FastAPI backend that implements a local RAG pipeline.

## What is implemented

- Resume upload for PDF or text files
- Role selection for `AI / ML Engineer` and `Backend Engineer`
- Resume parsing with skill, technology, domain, and seniority extraction
- Role-specific knowledge ingestion from Markdown corpora
- Chunking plus local embeddings with `sentence-transformers/all-MiniLM-L6-v2`
- Persistent vector retrieval with Chroma
- SQLite-backed interview session and transcript storage
- Adaptive question flow with traceable `query -> sources -> question -> answer -> summary`
- Structured session summary with grounded signals and transcript export

## Project structure

- `frontend/`: React + TanStack Start interview UI
- `backend/`: FastAPI app, services, persistence, ingestion, and knowledge base
- `.env.example`: environment variables for local configuration

## Backend run

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

The API starts at `http://127.0.0.1:8000` and exposes:

- `GET /api/health`
- `GET /api/roles`
- `POST /api/interviews/sessions`
- `POST /api/interviews/sessions/{session_id}/answers`
- `GET /api/interviews/sessions/{session_id}/summary`

## Frontend run

```bash
cd frontend
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8000/api` by default. Override it with:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

## Notes on the AI/ML core

- Knowledge is seeded from `backend/data/knowledge_base/*.md`
- Chroma persists vectors under `backend/data/chroma`
- The local embedding model is downloaded on first use
- The interview engine stores traceable retrieval evidence with every generated question

