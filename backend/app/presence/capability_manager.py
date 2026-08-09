import logging
from typing import Dict, Any, List
from app.memory.manager import memory_manager
from app.tools.manager import tool_manager
from app.planning.planner import hierarchical_planner
from app.vision.manager import vision_manager
from app.voice.manager import voice_manager
from app.agents.manager import agent_manager

logger = logging.getLogger("harika.presence.capability_manager")


class CapabilityManager:
    """Dynamically queries all registered subsystem managers to build unified capability summaries."""

    def __init__(self):
        self.memory_manager = memory_manager
        self.tool_manager = tool_manager
        self.planner = hierarchical_planner
        self.vision_manager = vision_manager
        self.voice_manager = voice_manager
        self.agent_manager = agent_manager

    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        capabilities = []

        try:
            tools_cap = self.tool_manager.get_capabilities()
            capabilities.append({
                "subsystem": "ToolManager",
                "name": "Desktop & Web Tools Engine",
                "features": [t.get("name", t.get("tool_name", "tool")) for t in tools_cap]
            })
        except Exception as e:
            logger.warning(f"[CapabilityManager] Error fetching ToolManager capabilities: {e}")

        for mgr in [self.memory_manager, self.planner, self.vision_manager, self.voice_manager, self.agent_manager]:
            try:
                cap = mgr.get_capabilities()
                capabilities.append(cap)
            except Exception as e:
                logger.warning(f"[CapabilityManager] Error fetching {mgr.__class__.__name__} capabilities: {e}")

        return capabilities

    def format_capability_summary(self) -> str:
        all_caps = self.get_all_capabilities()
        sections = []
        for cap in all_caps:
            sub_name = cap.get("name", cap.get("subsystem", "Subsystem"))
            features = cap.get("features", [])
            feat_str = ", ".join(features[:5]) if isinstance(features, list) else str(features)
            sections.append(f"• {sub_name}: {feat_str}")

        body = "\n".join(sections)
        return f"I can assist you across the following capabilities:\n\n{body}"


capability_manager = CapabilityManager()
