from dataclasses import dataclass
from typing import Callable

class ToolPermissionError(PermissionError): pass

@dataclass(frozen=True)
class Tool:
    name:str
    handler:Callable
    allowed_agents:frozenset[str]
    requires_approval:bool=False

class ToolRegistry:
    def __init__(self): self._tools={}
    def register(self,tool:Tool): self._tools[tool.name]=tool
    def invoke(self,name,agent,context):
        tool=self._tools.get(name)
        if not tool: raise ToolPermissionError(f"Tool '{name}' is not registered")
        if agent not in tool.allowed_agents: raise ToolPermissionError(f"{agent} is not permitted to call {name}")
        if tool.requires_approval and not context.get("approved"): return {"waiting_approval":True,"output":"Human approval required before controlled write"}
        return tool.handler(context)
    def manifest(self): return [{"name":t.name,"allowed_agents":sorted(t.allowed_agents),"requires_approval":t.requires_approval} for t in self._tools.values()]

registry=ToolRegistry()
registry.register(Tool("plan.decompose",lambda c:{"output":"Request decomposed into bounded agent steps with explicit tool and data-source scope"},frozenset({"Planner Agent"})))
registry.register(Tool("document.read",lambda c:{"output":"Document corpus available for scoped analysis"},frozenset({"Document Intelligence Agent"})))
registry.register(Tool("knowledge.search",lambda c:{"output":f"Retrieved {len(c.get('evidence',[]))} relevant private-knowledge chunks","evidence":c.get("evidence",[])},frozenset({"RAG Agent","Document Intelligence Agent"})))
registry.register(Tool("risk.assess",lambda c:{"output":"Potential hazards ranked by severity, likelihood, and evidence strength","evidence":c.get("evidence",[])},frozenset({"Risk Analysis Agent"})))
registry.register(Tool("evidence.verify",lambda c:{"output":"Evidence coverage verified; unsupported claims are excluded","evidence":c.get("evidence",[])},frozenset({"Verification Agent"})))
registry.register(Tool("response.compose",lambda c:{"output":"Evidence-backed recommendations prepared for operator review","evidence":c.get("evidence",[])},frozenset({"Planner Agent"})))
registry.register(Tool("controlled.write",lambda c:{"output":"Approved controlled action executed"},frozenset({"Tool Agent"}),True))
