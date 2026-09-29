import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
BASE = os.environ.get("SENTINEL_SMOKE_URL", "http://127.0.0.1:8011")
USERS = {"admin": "sentinel-admin", "approver": "sentinel-approver", "analyst": "sentinel-analyst", "viewer": "sentinel-viewer"}

SAMPLE = """
Site 7 safety inspection report - Pump House

1. Observation: A high risk hydraulic leak was identified near the primary pump seal.
   The leak is immediate and creates a slip hazard on the walkway.
2. Maintenance history shows the seal was replaced 14 months ago and the gasket failed twice.
3. SOP-OPS-14 requires isolation of the pump before any maintenance intervention.
4. Vibration readings are within tolerance; no critical defect was recorded on the secondary pump.
"""


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not condition:
        raise SystemExit(1)


def start_server():
    smoke_db = BACKEND / "data" / "smoke.db"
    smoke_chroma = BACKEND / "data" / "smoke_chroma"
    for path in (smoke_db,):
        if path.exists():
            path.unlink()
    if smoke_chroma.exists():
        import shutil

        shutil.rmtree(smoke_chroma, ignore_errors=True)
    env = dict(os.environ)
    env["SENTINEL_DATABASE_URL"] = f"sqlite:///{smoke_db}"
    env["SENTINEL_CHROMA_PATH"] = str(smoke_chroma)
    env["SENTINEL_LLM_PROVIDER"] = "mock"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8011", "--log-level", "warning"],
        cwd=str(BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            httpx.get(f"{BASE}/api/health", timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit("server did not start")


def login(client, username, password):
    response = client.post(
        f"{BASE}/api/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    check(f"login {username}", response.status_code == 200, response.text[:200])
    return response.json()


def main():
    proc = start_server()
    ws_uri = BASE.replace("http", "ws")
    try:
        with httpx.Client(timeout=120) as client:
            health = client.get(f"{BASE}/api/health").json()
            check("health", health["status"] == "operational", json.dumps(health["ai_adapter"]))

            admin = login(client, "admin", USERS["admin"])
            viewer = login(client, "viewer", USERS["viewer"])
            analyst = login(client, "analyst", USERS["analyst"])
            approver = login(client, "approver", USERS["approver"])
            headers = {"Authorization": f"Bearer {admin['access_token']}"}

            me = client.get(f"{BASE}/api/auth/me", headers=headers).json()
            check("rbac /api/auth/me", me["role"] == "admin" and "audit:read" in me["permissions"])

            forbidden = client.post(
                f"{BASE}/api/documents",
                files={"file": ("x.txt", b"hello")},
                headers={"Authorization": f"Bearer {viewer['access_token']}"},
            )
            check("rbac viewer cannot upload", forbidden.status_code == 403, forbidden.text)
            forbidden = client.get(
                f"{BASE}/api/audit", headers={"Authorization": f"Bearer {analyst['access_token']}"}
            )
            check("rbac analyst cannot read audit", forbidden.status_code == 403, forbidden.text)
            denied = client.post(f"{BASE}/api/chat", json={"query": "hello"}, headers={"Authorization": f"Bearer {viewer['access_token']}"})
            check("rbac viewer cannot chat", denied.status_code == 403, denied.text)

            upload = client.post(
                f"{BASE}/api/documents",
                files={"file": ("pump-house-inspection.txt", SAMPLE.encode())},
                headers=headers,
            )
            check("document upload", upload.status_code == 201, upload.text[:300])
            doc = upload.json()
            check("document indexed", doc["status"] == "indexed" and doc["chunk_count"] > 0, json.dumps(doc))

            detail = client.get(f"{BASE}/api/documents/{doc['id']}", headers=headers).json()
            check("document metadata", detail["filename"] == doc["filename"] and len(detail["chunks"]) > 0)

            search = client.post(
                f"{BASE}/api/knowledge/search",
                json={"query": "hydraulic leak maintenance SOP", "limit": 5},
                headers=headers,
            ).json()
            check("knowledge search evidence", len(search["evidence"]) > 0, f"{len(search['evidence'])} hits")

            chat = client.post(
                f"{BASE}/api/chat",
                json={"query": "Analyze the pump house inspection, identify high risk observations, compare with maintenance history and SOP, and recommend actions."},
                headers=headers,
            )
            check("chat api", chat.status_code == 200, chat.text[:300])
            chat = chat.json()
            check("chat response text", isinstance(chat["response"], str) and len(chat["response"]) > 40, chat["response"][:200])
            check("chat tasks", len(chat["tasks"]) == 9, f"{len(chat['tasks'])} tasks")
            statuses = {t["agent"]: t["status"] for t in chat["tasks"]}
            check("no task failed", "FAILED" not in statuses.values(), json.dumps(statuses))
            planner_tasks = [t for t in chat["tasks"] if t["tool"] == "plan.decompose"]
            check("planner first", planner_tasks and planner_tasks[0]["sequence"] == 1)
            last = chat["tasks"][-1]
            check("final response task", last["tool"] == "response.compose" and last["status"] == "COMPLETED")

            execution_id = chat["execution_id"]
            detail = client.get(f"{BASE}/api/executions/{execution_id}", headers=headers).json()
            check("execution detail", detail["status"] in {"COMPLETED", "WAITING_APPROVAL", "FAILED"}, detail["status"])

            tasks = client.get(f"{BASE}/api/tasks", params={"execution_id": execution_id}, headers=headers).json()
            check("task api", len(tasks) == 9)
            structured = tasks[0]["agent_output"]
            for field in ["agent_name", "task_id", "status", "reasoning_summary", "actions", "evidence", "output", "confidence", "timestamp"]:
                check(f"structured field {field}", field in structured)

            evidence = client.get(f"{BASE}/api/evidence", params={"execution_id": execution_id}, headers=headers).json()
            check("evidence api", len(evidence) >= 1 and "verification_status" in evidence[0], json.dumps([e["verification_status"] for e in evidence]))

            item = client.post(
                f"{BASE}/api/evidence",
                json={"title": "Operator note", "excerpt": "Leak observed during night shift", "execution_id": execution_id},
                headers=headers,
            )
            check("evidence create", item.status_code == 201, item.text[:200])

            audit = client.get(f"{BASE}/api/audit", headers=headers).json()
            actions = {row["action"] for row in audit}
            check(
                "audit covers agent actions",
                {"agent.started", "agent.completed", "execution.planned"} <= actions,
                json.dumps(sorted(actions)),
            )

            approvals = client.get(f"{BASE}/api/approvals", headers=headers).json()
            check("approval api", len(approvals) >= 1, f"{len(approvals)} approvals")
            approval = approvals[0]
            check("approval fields", approval["supporting_evidence"] and approval["requested_action"])

            decision = client.post(
                f"{BASE}/api/approvals/{approval['id']}/approved",
                json={"note": "authorized by smoke test"},
                headers={"Authorization": f"Bearer {approver['access_token']}"},
            )
            check("approver can decide", decision.status_code == 200, decision.text[:300])
            decision = decision.json()
            check("approval recorded", decision["approval"]["status"] == "approved")

            after = client.get(f"{BASE}/api/executions/{execution_id}", headers=headers).json()
            tool_tasks = [t for t in after["tasks"] if t["tool"] == "controlled.write"]
            check("controlled write executed after approval", tool_tasks and tool_tasks[0]["status"] in {"COMPLETED", "SKIPPED"}, json.dumps(tool_tasks))

            denied = client.post(
                f"{BASE}/api/approvals",
                json={"title": "nope"},
                headers={"Authorization": f"Bearer {analyst['access_token']}"},
            )
            check("rbac analyst cannot request approval", denied.status_code == 403, denied.text)

            users = client.get(f"{BASE}/api/users", headers=headers).json()
            check("admin user management", len(users) == 4, json.dumps([u["role"] for u in users]))

            agents = client.get(f"{BASE}/api/agents", headers=headers).json()
            check("agent registry", len(agents) == 6)
            for entry in agents:
                perms = entry["permissions"]
                for field in ["allowed_tools", "allowed_data_sources", "can_modify_data", "requires_human_approval"]:
                    check(f"permission {entry['name']} {field}", field in perms)

            tools = client.get(f"{BASE}/api/tools", headers=headers).json()
            names = {t["name"] for t in tools["tools"]}
            check("tool registry", {"plan.decompose", "controlled.write"} <= names, json.dumps(sorted(names)))

            ws_audit = client.get(f"{BASE}/api/audit", params={"action": "agent.completed", "limit": 5}, headers=headers).json()
            check("audit filters", len(ws_audit) >= 1 and all(r["action"] == "agent.completed" for r in ws_audit))

        async def ws_checks():
            import websockets

            async with websockets.connect(f"{ws_uri}/ws/agent-status?token={admin['access_token']}") as ws:
                snapshot = json.loads(await ws.recv())
                check("ws agent-status snapshot", snapshot["type"] == "snapshot" and len(snapshot["agents"]) == 6)
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                check("ws agent-status live event", event.get("type") in {"agent_status", "execution_status"}, json.dumps(event)[:200])

            async with websockets.connect(f"{ws_uri}/ws/executions?token={admin['access_token']}") as ws:
                await ws.send(json.dumps({"query": "Check the indexed SOP requirements and report residual risk."}))
                final = None
                while True:
                    message = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
                    if message.get("type") == "execution" and message.get("status") != "RUNNING":
                        final = message
                        if message.get("tasks"):
                            break
                check("ws executions final", final is not None and final["status"] in {"COMPLETED", "WAITING_APPROVAL"}, final["status"] if final else "none")
                check("ws executions evidence", "evidence" in final and "verification" in final)

            try:
                await websockets.connect(f"{ws_uri}/ws/agent-status?token=bad").__aenter__()
                check("ws rejects bad token", False)
            except Exception:
                check("ws rejects bad token", True)

        asyncio.run(ws_checks())
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    print("ALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
