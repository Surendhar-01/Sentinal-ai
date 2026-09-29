from .base import AgentPermissions, BaseAgent


class RAGAgent(BaseAgent):
    name = "RAG Agent"
    description = "Retrieves locally indexed passages for a scoped question"
    permissions = AgentPermissions(
        allowed_tools=["knowledge.search"],
        allowed_data_sources=["chroma_private_knowledge"],
    )

    def execute(self, task_id: int, description: str, context: dict):
        retrieve = context.get("retrieve")
        query = f"{context.get('query', '')} {description}".strip()
        evidence = retrieve(query, 5) if callable(retrieve) else list(context.get("evidence", []))
        actions = [
            "embedded the scoped question locally",
            "queried the private vector index",
            "returned passages with relevance scores",
        ]
        output = {
            "query": query,
            "matches": len(evidence),
            "sources": sorted({item.get("filename", "") for item in evidence if item.get("filename")}),
        }
        return self.result(
            task_id,
            "COMPLETED",
            f"Retrieved {len(evidence)} locally indexed passages ranked by semantic similarity.",
            actions,
            evidence,
            output,
            0.88 if evidence else 0.1,
        )
