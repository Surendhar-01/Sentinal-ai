import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..agents import PLAN, build_agents
from ..models import AgentTask, Approval, AuditEvent, Document, Execution, Finding
from .bus import bus
from .rag import embed
from .tools import registry
from .vector_store import vector_store

STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "WAITING_APPROVAL", "SKIPPED"}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "SKIPPED", "WAITING_APPROVAL"}


def utcnow() -> datetime:
    return datetime.utcnow()


def step_for(task) -> dict:
    if 0 < task.sequence <= len(PLAN):
        return PLAN[task.sequence - 1]
    return {
        "sequence": task.sequence,
        "agent": task.agent,
        "description": task.description,
        "objective": "",
        "tool": task.tool_name,
        "data_sources": [],
    }


def loads(raw, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


def serialize(task, step: dict | None = None) -> dict:
    step = step or step_for(task)
    payload = loads(task.output, {})
    payload = payload if isinstance(payload, dict) else {}
    return {
        "id": task.id,
        "execution_id": task.execution_id,
        "sequence": task.sequence,
        "agent": task.agent,
        "description": task.description,
        "status": task.status,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "output": payload.get("output", payload if payload else ""),
        "evidence": loads(task.evidence, []),
        "tool": task.tool_name,
        "data_sources": step.get("data_sources", []),
        "reasoning_summary": payload.get("reasoning_summary", ""),
        "actions": payload.get("actions", []),
        "confidence": payload.get("confidence"),
        "timestamp": payload.get("timestamp"),
        "agent_output": payload,
    }


def serialize_approval(approval: Approval | None) -> dict | None:
    if not approval:
        return None
    return {
        "id": approval.id,
        "execution_id": approval.execution_id,
        "title": approval.title,
        "risk": approval.risk,
        "status": approval.status,
        "recommendation": approval.recommendation,
        "explanation": approval.explanation or approval.rationale,
        "rationale": approval.rationale,
        "supporting_evidence": loads(approval.supporting_evidence, []),
        "agents_involved": loads(approval.agents_involved, []),
        "requested_action": approval.requested_action,
        "requested_by": approval.requested_by,
        "reviewer": approval.reviewer,
        "decision_note": approval.decision_note,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
    }


def audit(db: Session, actor: str, action: str, target: str = "", detail: dict | None = None) -> AuditEvent:
    event = AuditEvent(actor=actor, action=action, target=str(target), detail=json.dumps(detail or {}))
    db.add(event)
    return event


def merge_evidence(current: list[dict], incoming: list[dict]) -> list[dict]:
    merged = list(current)
    seen = {(item.get("document_id"), item.get("page"), item.get("excerpt")) for item in merged}
    for item in incoming:
        key = (item.get("document_id"), item.get("page"), item.get("excerpt"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged[:40]


def document_catalog(db: Session) -> list[dict]:
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "content_type": doc.content_type,
        }
        for doc in db.query(Document).order_by(Document.id.desc()).all()
    ]


def make_retriever():
    def retrieve(text: str, limit: int = 5) -> list[dict]:
        return vector_store().search(embed(text), limit)

    return retrieve


def create_execution(db: Session, query: str, username: str) -> tuple[Execution, list[AgentTask]]:
    execution = Execution(query=query, status="QUEUED", requested_by=username)
    db.add(execution)
    db.commit()
    db.refresh(execution)
    tasks = []
    for step in PLAN:
        task = AgentTask(
            execution_id=execution.id,
            sequence=step["sequence"],
            agent=step["agent"],
            description=step["description"],
            status="QUEUED",
            tool_name=step["tool"],
        )
        db.add(task)
        tasks.append(task)
    audit(
        db,
        username,
        "execution.planned",
        str(execution.id),
        {
            "query": query,
            "tasks": len(tasks),
            "steps": [{"agent": s["agent"], "tool": s["tool"]} for s in PLAN],
        },
    )
    db.commit()
    for task in tasks:
        db.refresh(task)
    return execution, tasks


async def _emit(send, event: dict) -> None:
    await send(event)
    stamp = utcnow().isoformat()
    if event.get("type") == "task":
        task = event.get("task", {})
        bus.publish(
            {
                "type": "agent_status",
                "execution_id": event.get("execution_id"),
                "task_id": task.get("id"),
                "agent": task.get("agent"),
                "tool": task.get("tool"),
                "status": task.get("status"),
                "timestamp": stamp,
            }
        )
    elif event.get("type") == "execution":
        bus.publish(
            {
                "type": "execution_status",
                "execution_id": event.get("execution_id"),
                "status": event.get("status"),
                "timestamp": stamp,
            }
        )


def _record_task(db: Session, task, result, step: dict) -> None:
    task.status = result.status
    task.output = json.dumps(result.model_dump())
    task.evidence = json.dumps(result.evidence)
    task.end_time = utcnow() if result.status in TERMINAL_STATUSES else None
    audit(
        db,
        result.agent_name,
        f"agent.{result.status.lower()}",
        str(task.id),
        {
            "execution_id": task.execution_id,
            "tool": step.get("tool"),
            "data_sources": step.get("data_sources", []),
            "status": result.status,
            "reasoning_summary": result.reasoning_summary,
            "actions": result.actions,
            "confidence": result.confidence,
            "output_timestamp": result.timestamp,
            "evidence_count": len(result.evidence),
        },
    )


def approval_gate(db: Session, execution, evidence, findings, verification, controlled, involved) -> Approval | None:
    needs_review = any(
        item.get("status") == "REQUIRES_HUMAN_REVIEW" or item.get("human_review_recommended")
        for item in verification
    )
    if not (needs_review or controlled):
        return None
    high_risk = any(item.get("risk_level") in {"HIGH", "CRITICAL"} for item in findings) or needs_review
    recommendation = (
        findings[0]["statement"]
        if findings
        else (verification[0]["finding"] if verification else "Review the agent recommendation before any change")
    )
    approval = Approval(
        execution_id=execution.id,
        title="High-impact AI recommendation" if needs_review else "Controlled action authorization",
        recommendation=recommendation,
        risk="high" if high_risk else "medium",
        status="pending",
        requested_by="Verification Agent" if needs_review else "Tool Agent",
        rationale=(
            "Independent verification requires accountable human authorization before this recommendation "
            "can be acted on."
            if needs_review
            else "The plan includes a controlled data change, which stays locked until a human records a decision."
        ),
        explanation=(
            "Evidence support was checked independently; operational impact still requires accountable "
            "authorization."
        ),
        supporting_evidence=json.dumps(evidence),
        agents_involved=json.dumps(sorted(set(involved))),
        requested_action=(
            "Authorize the controlled data change requested by the plan"
            if controlled
            else "Authorize the recommended safety intervention"
        ),
    )
    db.add(approval)
    audit(
        db,
        "Orchestrator",
        "approval.requested",
        str(execution.id),
        {"risk": approval.risk, "reason": "verification_gate" if needs_review else "controlled_action"},
    )
    db.commit()
    db.refresh(approval)
    return approval


def latest_approval(db: Session, execution_id: int) -> Approval | None:
    return (
        db.query(Approval)
        .filter(Approval.execution_id == execution_id)
        .order_by(Approval.id.desc())
        .first()
    )


def load_context_state(db: Session, execution) -> dict:
    tasks = (
        db.query(AgentTask).filter(AgentTask.execution_id == execution.id).order_by(AgentTask.sequence).all()
    )
    evidence: list[dict] = []
    findings: list[dict] = []
    verification: list[dict] = []
    plan_summary = ""
    controlled = False
    for task in tasks:
        payload = loads(task.output, {})
        if not isinstance(payload, dict):
            continue
        evidence = merge_evidence(evidence, loads(task.evidence, []))
        inner = payload.get("output") or {}
        if not isinstance(inner, dict):
            continue
        if task.tool_name == "plan.decompose":
            plan_summary = inner.get("summary", "")
            controlled = bool(inner.get("requires_controlled_action"))
        elif task.tool_name == "risk.assess":
            findings = inner.get("findings", [])
        elif task.tool_name == "evidence.verify":
            verification = inner.get("verification_results", [])
    return {
        "evidence": evidence,
        "findings": findings,
        "verification": verification,
        "plan_summary": plan_summary,
        "controlled_action_required": controlled,
        "approval": latest_approval(db, execution.id),
    }


def finalize_status(db: Session, execution, tasks) -> None:
    approval = latest_approval(db, execution.id)
    if any(task.status == "FAILED" for task in tasks):
        execution.status = "FAILED"
    elif approval and approval.status == "pending":
        execution.status = "WAITING_APPROVAL"
    elif any(task.status in {"RUNNING", "QUEUED"} for task in tasks):
        execution.status = "RUNNING"
    else:
        execution.status = "COMPLETED"
        execution.completed_at = execution.completed_at or utcnow()
    db.commit()


def execution_tasks(db: Session, execution_id: int) -> list[AgentTask]:
    return (
        db.query(AgentTask)
        .filter(AgentTask.execution_id == execution_id)
        .order_by(AgentTask.sequence)
        .all()
    )


def build_context(execution, step: dict, state: dict, documents: list[dict], retrieve, approved: bool) -> dict:
    approval = state.get("approval")
    return {
        "query": execution.query,
        "evidence": state.get("evidence", []),
        "findings": state.get("findings", []),
        "verification": state.get("verification", []),
        "documents": documents,
        "retrieve": retrieve,
        "tool": step["tool"],
        "phase": (
            "plan"
            if step["tool"] == "plan.decompose"
            else ("compose" if step["tool"] == "response.compose" else None)
        ),
        "approved": approved,
        "controlled_action_required": state.get("controlled_action_required", False),
        "approval": serialize_approval(approval),
        "plan_summary": state.get("plan_summary", ""),
    }


async def run_execution(db: Session, execution: Execution, tasks: list[AgentTask], send) -> None:
    agents = build_agents()
    retrieve = make_retriever()
    documents = document_catalog(db)
    execution.status = "RUNNING"
    db.commit()
    state = {
        "evidence": [],
        "findings": [],
        "verification": [],
        "plan_summary": "",
        "controlled_action_required": False,
        "approval": None,
    }
    involved: list[str] = []

    await _emit(
        send,
        {
            "type": "execution",
            "execution_id": execution.id,
            "status": "RUNNING",
            "tasks": [serialize(task) for task in tasks],
        },
    )

    for task in tasks:
        step = step_for(task)
        agent = agents[task.agent]
        task.status = "RUNNING"
        task.start_time = utcnow()
        db.commit()
        audit(db, task.agent, "agent.started", str(task.id), {"execution_id": execution.id, "tool": step["tool"]})
        db.commit()
        await _emit(send, {"type": "task", "execution_id": execution.id, "task": serialize(task, step)})
        approved = bool(
            state["approval"] and state["approval"].status == "approved"
        )
        context = build_context(execution, step, state, documents, retrieve, approved)
        try:
            registry.invoke(
                step["tool"],
                task.agent,
                {"query": execution.query, "evidence": state["evidence"], "approved": approved},
            )
            result = agent.run(
                task.id, task.description, context, tool=step["tool"], data_sources=step["data_sources"]
            )
            _record_task(db, task, result, step)
            involved.append(result.agent_name)
            inner = result.output if isinstance(result.output, dict) else {}
            if result.evidence:
                state["evidence"] = merge_evidence(state["evidence"], result.evidence)
            if step["tool"] == "plan.decompose":
                state["controlled_action_required"] = bool(inner.get("requires_controlled_action"))
                state["plan_summary"] = inner.get("summary", "")
            elif step["tool"] == "risk.assess":
                state["findings"] = inner.get("findings", [])
            elif step["tool"] == "evidence.verify":
                state["verification"] = inner.get("verification_results", [])
                for item in state["verification"]:
                    db.add(
                        Finding(
                            execution_id=execution.id,
                            statement=item["finding"],
                            verification_status=item["status"],
                            confidence=item["confidence"],
                            supporting_evidence=json.dumps(item["supporting_evidence"]),
                            contradictory_evidence=json.dumps(item["contradictory_evidence"]),
                            human_review_recommended=int(bool(item["human_review_recommended"])),
                        )
                    )
                state["approval"] = approval_gate(
                    db,
                    execution,
                    state["evidence"],
                    state["findings"],
                    state["verification"],
                    state["controlled_action_required"],
                    involved,
                )
            db.commit()
        except Exception as exc:
            task.status = "FAILED"
            task.output = json.dumps({"error": str(exc)})
            task.end_time = utcnow()
            audit(db, task.agent, "agent.failed", str(task.id), {"error": str(exc), "tool": step["tool"]})
            db.commit()
        await _emit(send, {"type": "task", "execution_id": execution.id, "task": serialize(task, step)})
        if task.status == "FAILED":
            break

    if state["approval"] is None:
        state["approval"] = approval_gate(
            db,
            execution,
            state["evidence"],
            state["findings"],
            state["verification"],
            state["controlled_action_required"],
            involved,
        )
    finalize_status(db, execution, tasks)
    await _emit(
        send,
        {
            "type": "execution",
            "execution_id": execution.id,
            "status": execution.status,
            "evidence_required": True,
            "evidence": state["evidence"],
            "verification": state["verification"],
            "approval": serialize_approval(state["approval"]),
            "tasks": [serialize(task) for task in tasks],
        },
    )
    audit(
        db,
        execution.requested_by,
        f"execution.{execution.status.lower()}",
        str(execution.id),
        {
            "tasks": len(tasks),
            "evidence": len(state["evidence"]),
            "findings": len(state["findings"]),
            "approval_id": state["approval"].id if state["approval"] else None,
        },
    )
    db.commit()


def apply_decision(db: Session, approval: Approval, decision: str) -> None:
    if approval.execution_id is None:
        return
    execution = db.get(Execution, approval.execution_id)
    if not execution:
        return
    tasks = execution_tasks(db, execution.id)
    agents = build_agents()
    retrieve = make_retriever()
    documents = document_catalog(db)

    for task in tasks:
        if task.status != "WAITING_APPROVAL":
            continue
        step = step_for(task)
        if decision == "rejected":
            task.status = "SKIPPED"
            task.output = json.dumps(
                {
                    "agent_name": task.agent,
                    "task_id": task.id,
                    "status": "SKIPPED",
                    "reasoning_summary": "A recorded human rejection blocks this controlled action.",
                    "actions": ["read the human decision", "left all data unchanged"],
                    "evidence": [],
                    "output": {"executed": False, "reason": "human approval rejected"},
                    "confidence": 1.0,
                    "timestamp": utcnow().isoformat(),
                }
            )
            task.end_time = utcnow()
            audit(db, task.agent, "agent.skipped", str(task.id), {"reason": "approval_rejected"})
            continue
        if decision != "approved":
            continue
        state = load_context_state(db, execution)
        state["approval"] = approval
        context = build_context(execution, step, state, documents, retrieve, True)
        try:
            registry.invoke(
                step["tool"],
                task.agent,
                {"query": execution.query, "evidence": state["evidence"], "approved": True},
            )
            result = agents[task.agent].run(
                task.id, task.description, context, tool=step["tool"], data_sources=step["data_sources"]
            )
            _record_task(db, task, result, step)
            if result.evidence:
                state["evidence"] = merge_evidence(state["evidence"], result.evidence)
        except Exception as exc:
            task.status = "FAILED"
            task.output = json.dumps({"error": str(exc)})
            task.end_time = utcnow()
            audit(db, task.agent, "agent.failed", str(task.id), {"error": str(exc)})
    if decision in {"approved", "rejected"}:
        finalize_status(db, execution, tasks)
    db.commit()
