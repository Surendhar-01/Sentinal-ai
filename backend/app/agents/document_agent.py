from ..adapters import SYSTEM_POLICY, get_adapter
from .base import AgentPermissions, BaseAgent


class DocumentAgent(BaseAgent):
    name = "Document Intelligence Agent"
    description = "Reads indexed documents and extracts observable, source-attributed findings"
    permissions = AgentPermissions(
        allowed_tools=["document.read", "knowledge.search"],
        allowed_data_sources=["uploaded_documents", "document_metadata"],
    )

    def execute(self, task_id: int, description: str, context: dict):
        tool = context.get("tool", "document.read")
        evidence = list(context.get("evidence", []))
        actions = ["opened the scoped document set"]
        if tool == "knowledge.search":
            retrieve = context.get("retrieve")
            if callable(retrieve):
                evidence = retrieve(f"{context.get('query', '')} {description}", 5)
            actions = [
                "embedded the query with the local embedding provider",
                "searched the private index for matching passages",
                "ranked passages by similarity",
            ]
        documents = context.get("documents", [])
        observations = [item.get("excerpt", "") for item in evidence[:4]]
        output = {
            "documents_read": [
                {"id": doc.get("id"), "filename": doc.get("filename"), "chunk_count": doc.get("chunk_count")}
                for doc in documents[:20]
            ],
            "observations": observations,
            "passages_read": len(evidence),
        }
        completion = get_adapter().generate(
            SYSTEM_POLICY,
            "Summarize in one sentence what was read from the private document set. No hidden chain-of-thought.",
            {"mode": "analysis", "topic": "the indexed document set", "evidence": evidence},
        )
        return self.result(
            task_id,
            "COMPLETED",
            completion.text,
            actions + ["recorded source-attributed observations"],
            evidence,
            output,
            0.82 if evidence else 0.2,
        )
