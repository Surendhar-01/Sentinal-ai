import re

from ..adapters import SYSTEM_POLICY, get_adapter
from .base import AgentPermissions, BaseAgent

HIGH_RISK_MARKERS = ("high risk", "critical", "immediate", "failure", "hazard", "unsafe", "severe")


def _lead(text: str, limit: int = 180) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    cut = clean[:limit].rsplit(" ", 1)[0]
    return f"{cut}..."


class AnalysisAgent(BaseAgent):
    name = "Risk Analysis Agent"
    description = "Classifies severity of evidence-linked observations and proposes controls"
    permissions = AgentPermissions(
        allowed_tools=["risk.assess"],
        allowed_data_sources=["retrieved_evidence", "maintenance_history", "sop_documents"],
    )

    def execute(self, task_id: int, description: str, context: dict):
        evidence = list(context.get("evidence", []))
        blob = " ".join(item.get("excerpt", "") for item in evidence).lower()
        high = any(marker in blob for marker in HIGH_RISK_MARKERS)
        risk = "HIGH" if high else "MEDIUM"
        if evidence:
            top = max(evidence, key=lambda item: item.get("relevance_score", 0))
            statement = (
                f"{risk} severity observation from {top.get('filename', 'indexed source')} "
                f"page {top.get('page', 1)}: {_lead(top.get('excerpt', ''))}"
            )
            source = {"filename": top.get("filename"), "page": top.get("page")}
        else:
            statement = (
                "Evidence gap: no indexed passage supports a severity judgement for this request, "
                "so the observation stays unclassified pending source material."
            )
            source = {}
        completion = get_adapter().generate(
            SYSTEM_POLICY,
            "State the severity classification in one sentence with its evidence basis. No hidden chain-of-thought.",
            {"mode": "analysis", "topic": statement, "evidence": evidence, "risk_level": risk},
        )
        findings = [
            {
                "statement": statement,
                "risk_level": risk,
                "summary": completion.text,
                "source": source,
                "requires_control": high,
            }
        ]
        actions = [
            "evaluated severity indicators in the retrieved passages",
            "compared the observation against operational impact markers",
            "created an evidence-linked finding",
        ]
        return self.result(
            task_id,
            "COMPLETED",
            completion.text,
            actions,
            evidence,
            {"findings": findings, "risk_level": risk},
            0.78 if evidence else 0.15,
        )
