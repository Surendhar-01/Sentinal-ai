import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .adapters import adapter_status, reset_adapter
from .agents import agent_manifest
from .config import settings
from .database import Base, SessionLocal, engine, ensure_columns, get_db
from .models import (
    AgentTask,
    Approval,
    AuditEvent,
    Chunk,
    Document,
    EvidenceItem,
    Execution,
    Finding,
    User,
)
from .security import (
    PERMISSIONS,
    ROLES,
    create_access_token,
    decode_token,
    get_current_user,
    hash_password,
    permissions_for,
    require,
    seed_users,
    verify_password,
)
from .services.bus import bus
from .services.orchestrator import (
    apply_decision,
    audit,
    create_execution,
    execution_tasks,
    loads,
    run_execution,
    serialize,
    serialize_approval,
)
from .services.rag import embed, extract_pages, split_pages
from .services.tools import registry
from .services.vector_store import vector_store, vector_store_kind

Base.metadata.create_all(engine)
MIGRATED_COLUMNS = ensure_columns(engine, Base.metadata)
app = FastAPI(title="SENTINEL-AI API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with SessionLocal() as seed_db:
    seed_users(seed_db)


def current_user(user: User = Depends(get_current_user)) -> User:
    return user


def write_audit(db: Session, actor: str, action: str, target: str = "", detail: dict | None = None):
    audit(db, actor, action, target, detail)
    db.commit()


def document_payload(doc: Document) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size": doc.size,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "searchable": doc.status == "indexed",
        "embedding_provider": doc.embedding_provider,
        "source_metadata": loads(doc.source_metadata, {}),
        "created_at": doc.created_at,
    }


def finding_payload(item: Finding) -> dict:
    return {
        "id": item.id,
        "execution_id": item.execution_id,
        "finding": item.statement,
        "statement": item.statement,
        "verification_status": item.verification_status,
        "confidence": item.confidence,
        "supporting_evidence": loads(item.supporting_evidence, []),
        "contradictory_evidence": loads(item.contradictory_evidence, []),
        "human_review_recommended": bool(item.human_review_recommended),
        "created_at": item.created_at,
    }


def evidence_item_payload(item: EvidenceItem) -> dict:
    return {
        "id": item.id,
        "execution_id": item.execution_id,
        "document_id": item.document_id,
        "title": item.title,
        "excerpt": item.excerpt,
        "reference": item.reference,
        "added_by": item.added_by,
        "created_at": item.created_at,
    }


def audit_payload(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "actor": event.actor,
        "action": event.action,
        "target": event.target,
        "detail": loads(event.detail, {}),
        "timestamp": event.timestamp,
    }


def approval_payload(item: Approval) -> dict:
    return serialize_approval(item)


def execution_summary(item: Execution) -> dict:
    return {
        "id": item.id,
        "query": item.query,
        "status": item.status,
        "requested_by": item.requested_by,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
    }


async def execute_request(body: "ExecutionRequest", user: User, db: Session) -> dict:
    execution, tasks = create_execution(db, body.query, user.username)
    events: list[dict] = []

    async def collect(event: dict):
        events.append(event)

    await run_execution(db, execution, tasks, collect)
    final = events[-1] if events else {}
    return {
        "execution_id": execution.id,
        "status": final.get("status", execution.status),
        "tasks": final.get("tasks", [serialize(task) for task in tasks]),
        "evidence": final.get("evidence", []),
        "verification": final.get("verification", []),
        "approval": final.get("approval"),
    }


@app.get("/api/health")
def health():
    ai = adapter_status()
    return {
        "status": "operational",
        "mode": "sovereign-local",
        "version": "2.0.0",
        "vector_store": settings.vector_store,
        "ai_adapter": ai,
        "external_ai_api": ai.get("external_service", False),
    }


@app.post("/api/auth/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(user.username, user.role)
    write_audit(db, user.username, "auth.login", user.username, {"role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "permissions": permissions_for(user.role),
    }


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {
        "username": user.username,
        "role": user.role,
        "permissions": permissions_for(user.role),
        "roles": list(ROLES),
    }


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    ai = adapter_status()
    return {
        "documents": db.query(Document).count(),
        "chunks": db.query(Chunk).count(),
        "pending_approvals": db.query(Approval).filter(Approval.status == "pending").count(),
        "audit_events": db.query(AuditEvent).count(),
        "agents_online": len(agent_manifest()),
        "tasks_executed": db.query(AgentTask).filter(AgentTask.status == "COMPLETED").count(),
        "verified_findings": db.query(Finding).filter(Finding.verification_status == "VERIFIED").count(),
        "executions": db.query(Execution).count(),
        "sovereignty_status": "EXTERNAL AI ENABLED" if ai["external_service"] else "ENFORCED",
        "local_model_status": ai["provider"].upper(),
        "ai_adapter": ai,
    }


@app.get("/api/agents")
def agents(user: User = Depends(require("agents:read"))):
    return agent_manifest()


@app.get("/api/agents/{agent_name}")
def agent_detail(agent_name: str, user: User = Depends(require("agents:read"))):
    for entry in agent_manifest():
        if entry["name"] == agent_name:
            return entry
    raise HTTPException(status_code=404, detail="Agent not found")


@app.get("/api/tools")
def tools(user: User = Depends(require("tools:read"))):
    return {"tools": registry.manifest(), "policy": "explicit_allowlist"}


@app.get("/api/documents")
def documents(db: Session = Depends(get_db), user: User = Depends(require("documents:read"))):
    return [document_payload(doc) for doc in db.query(Document).order_by(Document.id.desc()).all()]


@app.get("/api/documents/{document_id}")
def document_detail(document_id: int, db: Session = Depends(get_db), user: User = Depends(require("documents:read"))):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = (
        db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.position).limit(50).all()
    )
    payload = document_payload(doc)
    payload["chunks"] = [
        {"id": c.id, "page": c.page, "position": c.position, "text": c.text[:400]} for c in chunks
    ]
    payload["metadata"] = payload["source_metadata"]
    payload["indexed_at"] = doc.created_at
    return payload


@app.post("/api/documents", status_code=201)
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(require("documents:write")),
    db: Session = Depends(get_db),
):
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB")
    doc = Document(
        filename=file.filename or "unnamed",
        content_type=file.content_type or "",
        size=len(data),
        status="indexing",
        embedding_provider=settings.embedding_provider,
        source_metadata=json.dumps(
            {"origin": "user_upload", "owner": user.username, "content_type": file.content_type or ""}
        ),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        pages = extract_pages(doc.filename, data)
        pieces = split_pages(pages)
        store = vector_store()
        for position, (page, text) in enumerate(pieces):
            vector = embed(text)
            chunk = Chunk(
                document_id=doc.id, page=page, position=position, text=text, embedding="[]"
            )
            db.add(chunk)
            db.flush()
            store.add(chunk.id, doc.id, doc.filename, page, text, vector)
        doc.chunk_count = len(pieces)
        doc.status = "indexed"
        try:
            (settings.uploads_dir / f"{doc.id}_{doc.filename}").write_bytes(data)
        except OSError:
            pass
        write_audit(
            db,
            user.username,
            "document.indexed",
            str(doc.id),
            {"filename": doc.filename, "chunks": len(pieces), "size": len(data)},
        )
    except Exception as exc:
        doc.status = "failed"
        db.commit()
        write_audit(db, user.username, "document.failed", str(doc.id), {"error": str(exc)})
        raise HTTPException(status_code=422, detail=str(exc))
    return document_payload(doc)


@app.delete("/api/documents/{document_id}", status_code=200)
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(require("documents:delete"))):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        vector_store().delete_document(document_id)
    except Exception:
        pass
    db.query(Chunk).filter(Chunk.document_id == document_id).delete()
    db.query(EvidenceItem).filter(EvidenceItem.document_id == document_id).delete()
    db.delete(doc)
    write_audit(db, user.username, "document.deleted", str(document_id), {"filename": doc.filename})
    return {"status": "deleted", "id": document_id}


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@app.post("/api/knowledge/search")
def knowledge_search(
    body: SearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require("knowledge:search")),
):
    evidence = vector_store().search(embed(body.query), min(body.limit, 20))
    write_audit(
        db,
        user.username,
        "knowledge.searched",
        "",
        {"query": body.query, "evidence_count": len(evidence)},
    )
    return {"query": body.query, "evidence": evidence, "evidence_required": True}


class ExecutionRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


@app.post("/api/executions", status_code=201)
async def create_execution_api(
    body: ExecutionRequest,
    user: User = Depends(require("executions:run")),
    db: Session = Depends(get_db),
):
    return await execute_request(body, user, db)


@app.get("/api/executions")
def list_executions(db: Session = Depends(get_db), user: User = Depends(require("executions:read"))):
    return [execution_summary(item) for item in db.query(Execution).order_by(Execution.id.desc()).limit(100)]


@app.get("/api/executions/{execution_id}")
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("executions:read")),
):
    execution = db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    tasks = execution_tasks(db, execution_id)
    approval = (
        db.query(Approval).filter(Approval.execution_id == execution_id).order_by(Approval.id.desc()).first()
    )
    findings = db.query(Finding).filter(Finding.execution_id == execution_id).all()
    return {
        **execution_summary(execution),
        "tasks": [serialize(task) for task in tasks],
        "approval": serialize_approval(approval),
        "findings": [finding_payload(item) for item in findings],
    }


@app.post("/api/chat")
async def chat(
    body: ExecutionRequest,
    user: User = Depends(require("chat:run")),
    db: Session = Depends(get_db),
):
    result = await execute_request(body, user, db)
    tasks = result["tasks"]
    compose = next((t for t in reversed(tasks) if t.get("tool") == "response.compose"), tasks[-1] if tasks else {})
    agent_output = compose.get("agent_output") or {}
    inner = agent_output.get("output") or {}
    response_text = inner.get("response") if isinstance(inner, dict) else None
    if not response_text:
        response_text = agent_output.get("reasoning_summary") or "No response was composed for this request."
    return {
        "execution_id": result["execution_id"],
        "status": result["status"],
        "response": response_text,
        "structured": inner,
        "tasks": tasks,
        "evidence": result["evidence"],
        "verification": result["verification"],
        "approval": result["approval"],
        "notice": "AI recommendation only; approval status is reported separately.",
    }


@app.get("/api/tasks")
def tasks(
    execution_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("tasks:read")),
):
    query = db.query(AgentTask)
    if execution_id is not None:
        query = query.filter(AgentTask.execution_id == execution_id)
    if status:
        query = query.filter(AgentTask.status == status.upper())
    return [serialize(task) for task in query.order_by(AgentTask.id.desc()).limit(200)]


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: int, db: Session = Depends(get_db), user: User = Depends(require("tasks:read"))):
    task = db.get(AgentTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return serialize(task)


class TaskUpdate(BaseModel):
    status: str


ALLOWED_TASK_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "WAITING_APPROVAL", "SKIPPED"}


@app.patch("/api/tasks/{task_id}")
def update_task(
    task_id: int,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require("tasks:write")),
):
    if body.status not in ALLOWED_TASK_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid task status")
    task = db.get(AgentTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    previous = task.status
    task.status = body.status
    write_audit(
        db, user.username, "task.status_changed", str(task_id), {"from": previous, "to": body.status}
    )
    return serialize(task)


@app.get("/api/evidence")
def evidence(
    execution_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("evidence:read")),
):
    query = db.query(Finding)
    if execution_id is not None:
        query = query.filter(Finding.execution_id == execution_id)
    if status:
        query = query.filter(Finding.verification_status == status.upper())
    return [finding_payload(item) for item in query.order_by(Finding.id.desc()).limit(200)]


class EvidenceItemRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    excerpt: str = Field(min_length=1)
    execution_id: int | None = None
    document_id: int | None = None
    reference: str = ""


@app.get("/api/evidence/items")
def evidence_items(
    execution_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("evidence:read")),
):
    query = db.query(EvidenceItem)
    if execution_id is not None:
        query = query.filter(EvidenceItem.execution_id == execution_id)
    return [evidence_item_payload(item) for item in query.order_by(EvidenceItem.id.desc()).limit(200)]


@app.post("/api/evidence", status_code=201)
def create_evidence_item(
    body: EvidenceItemRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require("evidence:write")),
):
    if body.document_id is not None and not db.get(Document, body.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    if body.execution_id is not None and not db.get(Execution, body.execution_id):
        raise HTTPException(status_code=404, detail="Execution not found")
    item = EvidenceItem(
        execution_id=body.execution_id,
        document_id=body.document_id,
        title=body.title,
        excerpt=body.excerpt,
        reference=body.reference,
        added_by=user.username,
    )
    db.add(item)
    db.flush()
    write_audit(db, user.username, "evidence.recorded", str(item.id), {"title": body.title})
    return evidence_item_payload(item)


@app.get("/api/evidence/{finding_id}")
def evidence_detail(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("evidence:read")),
):
    item = db.get(Finding, finding_id)
    if not item:
        raise HTTPException(status_code=404, detail="Evidence finding not found")
    return finding_payload(item)


@app.get("/api/approvals")
def approvals(db: Session = Depends(get_db), user: User = Depends(require("approvals:read"))):
    return [approval_payload(item) for item in db.query(Approval).order_by(Approval.id.desc()).all()]


@app.get("/api/approvals/{approval_id}")
def approval_detail(
    approval_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("approvals:read")),
):
    item = db.get(Approval, approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval_payload(item)


class ApprovalRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    recommendation: str = ""
    requested_action: str = ""
    risk: str = "high"
    execution_id: int | None = None
    supporting_evidence: list[dict] = Field(default_factory=list)
    agents_involved: list[str] = Field(default_factory=list)
    rationale: str = ""


@app.post("/api/approvals", status_code=201)
def request_approval(
    body: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require("approvals:request")),
):
    item = Approval(
        execution_id=body.execution_id,
        title=body.title,
        recommendation=body.recommendation or body.title,
        requested_action=body.requested_action,
        risk=body.risk,
        status="pending",
        requested_by=user.username,
        rationale=body.rationale or "Human authorization requested by an authenticated operator.",
        supporting_evidence=json.dumps(body.supporting_evidence),
        agents_involved=json.dumps(body.agents_involved),
    )
    db.add(item)
    db.flush()
    write_audit(db, user.username, "approval.requested", str(item.id), {"title": body.title, "risk": body.risk})
    db.commit()
    return approval_payload(item)


class Decision(BaseModel):
    note: str = ""


@app.post("/api/approvals/{approval_id}/{decision}")
def decide(
    approval_id: int,
    decision: str,
    body: Decision | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("approvals:decide")),
):
    if decision not in {"approved", "rejected", "more_evidence_requested"}:
        raise HTTPException(status_code=400, detail="Invalid decision")
    item = db.get(Approval, approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Approval not found")
    note = body.note if body else ""
    item.status = decision
    item.reviewer = user.username
    item.decision_note = note
    item.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    write_audit(
        db,
        user.username,
        f"approval.{decision}",
        str(approval_id),
        {"note": note, "recommendation": item.recommendation, "execution_id": item.execution_id},
    )
    if decision in {"approved", "rejected"}:
        apply_decision(db, item, decision)
    db.commit()
    return {
        "status": decision,
        "human_decision": True,
        "approval": approval_payload(item),
        "execution_id": item.execution_id,
    }


@app.get("/api/audit")
def audit_log(
    actor: str | None = None,
    action: str | None = None,
    target: str | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require("audit:read")),
):
    query = db.query(AuditEvent)
    if actor:
        query = query.filter(AuditEvent.actor == actor)
    if action:
        query = query.filter(AuditEvent.action == action)
    if target:
        query = query.filter(AuditEvent.target == str(target))
    return [audit_payload(event) for event in query.order_by(AuditEvent.id.desc()).limit(limit)]


@app.get("/api/audit/{event_id}")
def audit_detail(event_id: int, db: Session = Depends(get_db), user: User = Depends(require("audit:read"))):
    event = db.get(AuditEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return audit_payload(event)


def safe_settings_payload() -> dict:
    ai = adapter_status()
    return {
        "runtime": {"api_version": app.version, "environment": "on-premise", "status": "operational"},
        "ai": {
            "provider": settings.llm_provider,
            "active_adapter": ai["provider"],
            "model": settings.groq_model if settings.llm_provider == "groq" else settings.llm_model,
            "external_service": ai.get("external_service", False),
            "external_ai_allowed": settings.allow_external_ai,
            "groq_key_configured": bool(settings.groq_api_key),
            "fallback": ai["fallback"],
        },
        "knowledge": {
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
        "vector_store": vector_store_kind(),
        },
        "security": {
            "jwt_ttl_hours": settings.jwt_ttl_hours,
            "cors_origins": settings.cors_origins.split(","),
            "rbac_enabled": True,
            "audit_enabled": True,
            "secret_configured": settings.secret_key != "dev-only-change-me",
        },
    }


@app.get("/api/settings")
def read_settings(user: User = Depends(require("users:read"))):
    return safe_settings_payload()


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = Field(default=None, max_length=120)
    groq_model: str | None = Field(default=None, max_length=120)
    allow_external_ai: bool | None = None
    jwt_ttl_hours: int | None = Field(default=None, ge=1, le=72)


@app.patch("/api/settings")
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require("users:write")),
):
    changes = {}
    if body.llm_provider is not None:
        provider = body.llm_provider.lower()
        if provider not in {"auto", "mock", "ollama", "groq"}:
            raise HTTPException(status_code=400, detail="Provider must be auto, mock, ollama, or groq")
        changes["llm_provider"] = {"from": settings.llm_provider, "to": provider}
        settings.llm_provider = provider
    for field in ("llm_model", "groq_model", "allow_external_ai", "jwt_ttl_hours"):
        value = getattr(body, field)
        if value is not None:
            changes[field] = {"from": getattr(settings, field), "to": value}
            setattr(settings, field, value)
    reset_adapter()
    write_audit(db, user.username, "settings.updated", "runtime", changes)
    return {"message": "Runtime settings updated; use .env to persist across restarts", "settings": safe_settings_payload()}


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    role: str = "analyst"


class UserUpdate(BaseModel):
    role: str | None = None
    password: str | None = None


@app.get("/api/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require("users:read"))):
    return [
        {"id": u.id, "username": u.username, "role": u.role, "permissions": permissions_for(u.role)}
        for u in db.query(User).order_by(User.id).all()
    ]


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), user: User = Depends(require("users:write"))):
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(ROLES)}")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    new_user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(new_user)
    write_audit(db, user.username, "user.created", body.username, {"role": body.role})
    db.commit()
    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}


@app.patch("/api/users/{user_id}")
def update_user(
    user_id: int, body: UserUpdate, db: Session = Depends(get_db), user: User = Depends(require("users:write"))
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    changes = {}
    if body.role:
        if body.role not in ROLES:
            raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(ROLES)}")
        changes["role"] = {"from": target.role, "to": body.role}
        target.role = body.role
    if body.password:
        target.password_hash = hash_password(body.password)
        changes["password"] = "reset"
    write_audit(db, user.username, "user.updated", target.username, changes)
    db.commit()
    return {"id": target.id, "username": target.username, "role": target.role}


def agent_status_snapshot(db: Session) -> dict:
    agents = agent_manifest()
    latest: dict[str, AgentTask] = {}
    for task in db.query(AgentTask).order_by(AgentTask.id.desc()).limit(50):
        latest.setdefault(task.agent, task)
    for entry in agents:
        task = latest.get(entry["name"])
        entry["current_task"] = serialize(task) if task else None
        entry["state"] = task.status if task else "IDLE"
    return {
        "type": "snapshot",
        "agents": agents,
        "subscribers": bus.subscriber_count,
        "pending_approvals": db.query(Approval).filter(Approval.status == "pending").count(),
        "running_executions": db.query(Execution).filter(Execution.status == "RUNNING").count(),
        "ai_adapter": adapter_status(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def authenticate_socket(token: str | None) -> dict | None:
    if not token:
        return None
    return decode_token(token)


@app.websocket("/ws/executions")
async def execution_socket(ws: WebSocket):
    payload = authenticate_socket(ws.query_params.get("token"))
    if not payload:
        await ws.close(code=4401)
        return
    await ws.accept()
    username = payload.get("sub", "unknown")
    try:
        while True:
            message = json.loads(await ws.receive_text())
            query = (message.get("query") or "").strip()
            if not query:
                await ws.send_json({"type": "error", "message": "Query is required"})
                continue
            db = SessionLocal()
            try:
                execution, tasks = create_execution(db, query, username)
                await run_execution(db, execution, tasks, ws.send_json)
            finally:
                db.close()
    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "message": "Malformed payload"})


@app.websocket("/ws/agent-status")
async def agent_status_socket(ws: WebSocket):
    payload = authenticate_socket(ws.query_params.get("token"))
    if not payload:
        await ws.close(code=4401)
        return
    await ws.accept()
    db = SessionLocal()
    try:
        snapshot = agent_status_snapshot(db)
    finally:
        db.close()
    await ws.send_json(snapshot)
    queue = bus.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
            except asyncio.TimeoutError:
                await ws.send_json(
                    {
                        "type": "heartbeat",
                        "subscribers": bus.subscriber_count,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                continue
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)


@app.get("/api/permissions")
def permission_matrix(user: User = Depends(current_user)):
    return {
        "roles": list(ROLES),
        "matrix": PERMISSIONS,
        "your_role": user.role,
        "your_permissions": permissions_for(user.role),
    }
