from ..adapters import SYSTEM_POLICY, get_adapter
from .base import AgentPermissions, BaseAgent
from .plan import PLAN, requires_controlled_action


class PlannerAgent(BaseAgent):
    name = "Planner Agent"
    description = "Decomposes requests into bounded steps and composes the final cited response"
    permissions = AgentPermissions(
        allowed_tools=["plan.decompose", "response.compose"],
        allowed_data_sources=["task_outputs", "verified_findings"],
    )

    def execute(self, task_id: int, description: str, context: dict):
        if context.get("phase") == "compose":
            return self._compose(task_id, description, context)
        return self._plan(task_id, description, context)

    def _plan(self, task_id: int, description: str, context: dict):
        query = context.get("query", "")
        controlled = requires_controlled_action(query)
        steps = [
            {
                "sequence": step["sequence"],
                "agent": step["agent"],
                "objective": step["objective"],
                "tool": step["tool"],
                "data_sources": step["data_sources"],
            }
            for step in PLAN
        ]
        completion = get_adapter().generate(
            SYSTEM_POLICY,
            "Produce a one-paragraph bounded plan summary for this request. "
            "List agents, tools, and data sources only. No hidden chain-of-thought.",
            {"mode": "plan", "query": query, "steps": steps, "requires_controlled_action": controlled},
        )
        output = {
            "plan": steps,
            "summary": completion.text,
            "requires_controlled_action": controlled,
            "approval_gate": "human approval is required before any controlled data change",
            "provider": completion.provider,
        }
        return self.result(
            task_id,
            "COMPLETED",
            "Produced a bounded plan naming each agent, tool, and data source before any work ran.",
            [
                "decomposed the request into ordered agent steps",
                "assigned an explicit allow-listed tool per step",
                "limited each step to permitted data sources",
                "flagged whether a controlled data change is in scope",
            ],
            [],
            output,
            0.9,
        )

    def _compose(self, task_id: int, description: str, context: dict):
        evidence = context.get("evidence", [])
        findings = context.get("findings", [])
        verification = context.get("verification", [])
        approval = context.get("approval")
        completion = get_adapter().generate(
            SYSTEM_POLICY,
            "Compose the final operator-facing response from the verified findings and cited evidence. "
            "Two to six sentences, cite document and page, state the approval state. No hidden chain-of-thought.",
            {
                "mode": "response",
                "query": context.get("query", ""),
                "evidence": evidence,
                "findings": findings,
                "verification": verification,
                "approval": approval,
            },
        )
        citations = [
            {"filename": item.get("filename"), "page": item.get("page"), "relevance_score": item.get("relevance_score")}
            for item in evidence[:6]
        ]
        confidences = [item.get("confidence", 0.5) for item in verification] or [0.5]
        output = {
            "response": completion.text,
            "citations": citations,
            "plan_summary": context.get("plan_summary", ""),
            "approval": approval,
            "provider": completion.provider,
            "notice": "AI recommendation only; approval status is reported separately.",
        }
        return self.result(
            task_id,
            "COMPLETED",
            "Composed a concise cited response from verified task outputs only.",
            [
                "assembled verified findings",
                "cited source passages",
                "stated the human approval state",
            ],
            evidence,
            output,
            round(sum(confidences) / len(confidences), 3),
        )
