import logging
from typing import Dict, Any, List, Optional
from app.router.schemas import EngineCapability, IntentType, EnginePriority

logger = logging.getLogger("harika.router.registry")


class RouterRegistry:
    """Dynamic Plugin Registry for HARIKA Subsystems without hardcoding engine or tool names."""

    def __init__(self):
        self._capabilities: Dict[str, EngineCapability] = {}
        self._managers: Dict[str, Any] = {}
        self._priorities: Dict[str, EnginePriority] = {
            "SystemManager": EnginePriority.SYSTEM,
            "MemoryManager": EnginePriority.MEMORY,
            "ToolManager": EnginePriority.TOOLS,
            "VisionManager": EnginePriority.VISION,
            "HierarchicalPlanner": EnginePriority.PLANNING,
            "AgentManager": EnginePriority.AGENTS,
            "VoiceManager": EnginePriority.VOICE,
            "CognitionManager": EnginePriority.CHAT,
        }

        self.register_default_engines()

    def register_default_engines(self) -> None:
        try:
            from app.cognition.manager import cognition_manager
            self.register_engine("CognitionManager", cognition_manager, EngineCapability(engine="CognitionManager", intents=[IntentType.CHAT]))
        except Exception:
            pass

        try:
            from app.memory.manager import memory_manager
            self.register_engine("MemoryManager", memory_manager, EngineCapability(engine="MemoryManager", intents=[IntentType.MEMORY_STORE, IntentType.MEMORY_QUERY, IntentType.MEMORY_UPDATE]))
        except Exception:
            pass

        try:
            from app.tools.manager import tool_manager
            self.register_engine("ToolManager", tool_manager, EngineCapability(engine="ToolManager", intents=[IntentType.TOOL_EXECUTION]))
        except Exception:
            pass

        try:
            from app.vision.manager import vision_manager
            self.register_engine("VisionManager", vision_manager, EngineCapability(engine="VisionManager", intents=[IntentType.VISION_ANALYSIS]))
        except Exception:
            pass

        try:
            from app.agents.manager import agent_manager
            self.register_engine("AgentManager", agent_manager, EngineCapability(engine="AgentManager", intents=[IntentType.AGENT_START, IntentType.AGENT_STATUS, IntentType.AGENT_CONTINUE]))
        except Exception:
            pass

        try:
            from app.planning.planner import hierarchical_planner
            self.register_engine("HierarchicalPlanner", hierarchical_planner, EngineCapability(engine="HierarchicalPlanner", intents=[IntentType.PLAN_CREATION, IntentType.PLAN_QUERY]))
        except Exception:
            pass

        try:
            from app.voice.manager import voice_manager
            self.register_engine("VoiceManager", voice_manager, EngineCapability(engine="VoiceManager", intents=[IntentType.VOICE_COMMAND]))
        except Exception:
            pass

    def register_engine(self, engine_name: str, manager_instance: Any, capability: EngineCapability) -> None:
        self._managers[engine_name] = manager_instance
        self._capabilities[engine_name] = capability
        logger.info(f"[RouterRegistry] Registered engine '{engine_name}' (version {capability.version}) for intents: {[i.value for i in capability.intents]}.")

    def get_capabilities(self) -> List[EngineCapability]:
        return list(self._capabilities.values())

    def get_manager(self, engine_name: str) -> Optional[Any]:
        return self._managers.get(engine_name)

    def get_priority(self, engine_name: str) -> EnginePriority:
        return self._priorities.get(engine_name, EnginePriority.CHAT)


router_registry = RouterRegistry()

