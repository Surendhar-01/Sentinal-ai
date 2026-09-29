# SENTINEL-AI — Sovereign On-Premise Agentic AI Workbench

SENTINEL-AI is a full-stack prototype for confidential industrial environments. It demonstrates secure document ingestion, private retrieval, evidence objects, visible multi-agent execution, human approval gates, RBAC, WebSocket events, and audit trails.

## Architecture

- `frontend/`: React + Vite enterprise operations console
- `backend/`: FastAPI, SQLAlchemy, SQLite, JWT/RBAC, document pipeline
- Embeddings are configurable: deterministic local hash embeddings work with no model download; set `SENTINEL_EMBEDDING_PROVIDER=ollama` for a local Ollama embedding endpoint.
- Embeddings and chunk text are persisted in a local Chroma collection; SQLite stores document metadata, task state, approvals, users, and audit records.
- The orchestration service creates seven durable tasks, streams `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, and `WAITING_APPROVAL` states, and attaches evidence objects to grounded outputs.
- Agents cannot execute arbitrary functions. The explicit tool registry maps every tool to permitted agents and marks consequential tools as approval-gated.
- Six concrete modules under `backend/app/agents/` implement one typed agent interface. Stored reasoning is limited to concise summaries and observable actions; hidden chain-of-thought is never persisted or returned.
- Independent verification assigns `VERIFIED`, `PARTIALLY_VERIFIED`, `UNSUPPORTED`, `CONTRADICTED`, or `REQUIRES_HUMAN_REVIEW`. A finding cannot be verified without supporting evidence.
- High-impact recommendations create separate approval records with recommendation, evidence, involved agents, requested action, and human decision history.

## Run

Backend (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20+), in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. MVP login: `admin` / `sentinel-admin`.

Copy each `.env.example` to `.env` to change API URLs or embedding configuration. Replace the development secret and seeded credentials before any non-local deployment.

### Groq analysis provider

Groq is supported through its OpenAI-compatible chat-completions endpoint. Because this sends request context and retrieved evidence outside the on-premise boundary, it is disabled unless explicitly allowed:

```env
SENTINEL_LLM_PROVIDER=groq
SENTINEL_ALLOW_EXTERNAL_AI=true
SENTINEL_GROQ_API_KEY=your-rotated-key
SENTINEL_GROQ_MODEL=openai/gpt-oss-120b
```

If Groq fails or is unavailable, the resilient adapter uses the deterministic local provider so the application remains operational. Never commit `.env`.

## Core APIs

- `POST /api/documents` — extract, chunk, embed, and index PDF/TXT/DOCX
- `POST /api/knowledge/search` — return source-grounded evidence objects
- `POST /api/chat` — execute the full evidence/verification/approval-aware workflow
- `POST /api/executions` — execute and return structured agent tasks
- `GET/PATCH /api/tasks` — inspect and administer durable tasks
- `GET /api/evidence` — inspect verified findings and contradictory evidence
- `GET /api/agents` — inspect agent permissions and runtime status
- `GET /api/tools` — inspect the agent/tool permission manifest
- `GET /api/executions/{id}` — retrieve durable task details and evidence
- `WS /ws/executions?token=<jwt>` — authenticated live workflow execution
