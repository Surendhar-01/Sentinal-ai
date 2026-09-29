from .base import AgentOutput, AgentPermissionError, AgentPermissions, BaseAgent
from .plan import PLAN, requires_controlled_action
from .planner import PlannerAgent
from .document_agent import DocumentAgent
from .rag_agent import RAGAgent
from .analysis_agent import AnalysisAgent
from .tool_agent import ToolAgent
from .verifier import VerificationAgent

AGENT_CLASSES = {
    "Planner Agent": PlannerAgent,
    "Document Intelligence Agent": DocumentAgent,
    "RAG Agent": RAGAgent,
    "Risk Analysis Agent": AnalysisAgent,
    "Tool Agent": ToolAgent,
    "Verification Agent": VerificationAgent,
}


def build_agents() -> dict[str, BaseAgent]:
    return {name: cls() for name, cls in AGENT_CLASSES.items()}


def agent_manifest() -> list[dict]:
    return [agent.describe() for agent in build_agents().values()]


__all__ = [
    "AgentOutput",
    "AgentPermissions",
    "AgentPermissionError",
    "BaseAgent",
    "PlannerAgent",
    "DocumentAgent",
    "RAGAgent",
    "AnalysisAgent",
    "ToolAgent",
    "VerificationAgent",
    "AGENT_CLASSES",
    "build_agents",
    "agent_manifest",
    "PLAN",
    "requires_controlled_action",
]
