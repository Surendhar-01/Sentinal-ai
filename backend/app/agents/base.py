from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AgentPermissions(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_data_sources: list[str] = Field(default_factory=list)
    can_modify_data: bool = False
    requires_human_approval: bool = False


class AgentOutput(BaseModel):
    agent_name: str
    task_id: int
    status: str
    reasoning_summary: str
    actions: list[str]
    evidence: list[dict]
    output: object
    confidence: float = Field(ge=0, le=1)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentPermissionError(PermissionError):
    pass


class BaseAgent(ABC):
    name: str = "Base Agent"
    description: str = ""
    permissions: AgentPermissions = AgentPermissions()

    @abstractmethod
    def execute(self, task_id: int, description: str, context: dict) -> AgentOutput: ...

    def result(self, task_id, status, summary, actions, evidence, output, confidence) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            task_id=task_id,
            status=status,
            reasoning_summary=summary,
            actions=actions,
            evidence=evidence,
            output=output,
            confidence=confidence,
        )

    def ensure_tool(self, tool: str) -> None:
        if tool not in self.permissions.allowed_tools:
            raise AgentPermissionError(f"{self.name} is not permitted to use tool '{tool}'")

    def ensure_data_sources(self, sources: list[str]) -> None:
        allowed = set(self.permissions.allowed_data_sources)
        denied = [source for source in sources if source not in allowed]
        if denied:
            raise AgentPermissionError(
                f"{self.name} is not permitted to read data source(s): {', '.join(denied)}"
            )

    def run(
        self,
        task_id: int,
        description: str,
        context: dict,
        tool: str | None = None,
        data_sources: list[str] | None = None,
    ) -> AgentOutput:
        if tool:
            self.ensure_tool(tool)
        if data_sources:
            self.ensure_data_sources(data_sources)
        result = self.execute(task_id, description, context)
        if not isinstance(result, AgentOutput):
            raise TypeError(f"{self.name} must return a structured AgentOutput")
        if result.agent_name != self.name:
            raise ValueError(f"{self.name} returned output for '{result.agent_name}'")
        if result.task_id != task_id:
            raise ValueError(f"{self.name} returned output for task {result.task_id}")
        if self.permissions.can_modify_data and self.permissions.requires_human_approval:
            if not context.get("approved") and result.status != "WAITING_APPROVAL":
                raise AgentPermissionError(
                    f"{self.name} cannot report '{result.status}' without a recorded human approval"
                )
        return result

    def describe(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions.model_dump(),
            "status": "ONLINE",
        }
