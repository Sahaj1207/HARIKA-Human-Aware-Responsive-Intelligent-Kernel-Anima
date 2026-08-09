import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.router.schemas import IntentType, EnginePriority


class ActionNode(BaseModel):
    id: str = Field(default_factory=lambda: f"node-{uuid.uuid4().hex[:8]}")
    intent: IntentType
    engine: str
    action: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    status: str = "pending"  # pending, executing, completed, failed
    result: Optional[Any] = None
    priority: EnginePriority = EnginePriority.CHAT


class ActionGraph(BaseModel):
    graph_id: str = Field(default_factory=lambda: f"graph-{uuid.uuid4().hex[:8]}")
    nodes: List[ActionNode] = Field(default_factory=list)

    def add_node(self, node: ActionNode) -> None:
        self.nodes.append(node)

    def get_executable_nodes(self) -> List[ActionNode]:
        completed_ids = {n.id for n in self.nodes if n.status == "completed"}
        return [
            n for n in self.nodes
            if n.status == "pending" and all(d in completed_ids for d in n.dependencies)
        ]
