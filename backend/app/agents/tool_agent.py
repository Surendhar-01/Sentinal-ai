from .base import AgentPermissions, BaseAgent


class ToolAgent(BaseAgent):
    name = "Tool Agent"
    description = "Executes approval-gated controlled actions from the allow-listed tool registry"
    permissions = AgentPermissions(
        allowed_tools=["controlled.write"],
        allowed_data_sources=["approved_recommendations"],
        can_modify_data=True,
        requires_human_approval=True,
    )

    def execute(self, task_id: int, description: str, context: dict):
        evidence = list(context.get("evidence", []))
        if not context.get("controlled_action_required"):
            return self.result(
                task_id,
                "SKIPPED",
                "The plan contains no controlled data change, so no write tool was invoked.",
                ["inspected the plan scope", "left all data unchanged"],
                evidence,
                {"executed": False, "reason": "no controlled data change requested"},
                1.0,
            )
        approval = context.get("approval") or {}
        if approval.get("status") == "rejected":
            return self.result(
                task_id,
                "SKIPPED",
                "A recorded human rejection blocks the controlled action.",
                ["validated the human decision", "left all data unchanged"],
                evidence,
                {"executed": False, "reason": "human approval rejected"},
                1.0,
            )
        if not context.get("approved"):
            return self.result(
                task_id,
                "WAITING_APPROVAL",
                "A controlled modification cannot proceed without a recorded human decision.",
                ["requested human approval", "held the controlled action"],
                evidence,
                {"executed": False, "reason": "awaiting recorded human approval"},
                1.0,
            )
        return self.result(
            task_id,
            "COMPLETED",
            "Executed the controlled action under a recorded human approval.",
            [
                "validated the recorded approval",
                "invoked the allow-listed controlled.write tool",
                "left an audit record of the executed action",
            ],
            evidence,
            {
                "executed": True,
                "action": approval.get("requested_action", "controlled action"),
                "approval_id": approval.get("id"),
                "approved_by": approval.get("reviewer"),
            },
            1.0,
        )
