import logging
from typing import Any, Dict, Optional
from app.router.schemas import IntentType
from app.router.action_graph import ActionNode
from app.router.registry import router_registry

logger = logging.getLogger("harika.router.resolver")


class SubsystemResolver:
    """Delegates execution strictly through registered Subsystem Facade Managers."""

    async def execute_node(self, node: ActionNode, user_id: str = "default") -> Any:
        mgr = router_registry.get_manager(node.engine)
        found = "YES" if mgr is not None else "NO"
        keys = list(router_registry._managers.keys())
        mgr_cls = mgr.__class__.__name__ if mgr else "None"
        logger.info(
            f"\n=========================================================\nENGINE RESOLUTION\n"
            f"Resolving Engine...\nEngine Name: {node.engine}\nRegistry Keys: {keys}\n"
            f"Engine Found?: {found}\nResolved Manager Class: {mgr_cls}\n"
            f"========================================================="
        )

        logger.info(f"Executing...\nManager: {node.engine}\nMethod: {node.action}\nArguments: {node.arguments}")

        # 1. ToolManager
        if node.engine == "ToolManager":
            from app.tools.manager import tool_manager
            query = node.arguments.get("query", "")
            action_plan = tool_manager.plan_action(query)
            if action_plan.actions:
                res = await tool_manager.execute_planned_action(action_plan)
                if res:
                    tool_act = action_plan.actions[0].tool_name if action_plan.actions else (node.action or "tool")
                    return {
                        "status": "success" if (res.success and getattr(res, "verified", True)) else "failed",
                        "success": res.success,
                        "verified": getattr(res, "verified", res.success),
                        "pid": getattr(res, "pid", None),
                        "process_name": getattr(res, "process_name", None),
                        "tool": tool_act,
                        "result": res.output if res.output is not None else res.error,
                        "error": res.error
                    }

            return {
                "status": "failed",
                "success": False,
                "verified": False,
                "tool": query,
                "error": f"No matching desktop tool or application found for '{query}'."
            }






        # 2. MemoryManager
        elif node.engine == "MemoryManager":
            from app.memory.manager import memory_manager
            from app.memory.models import MemoryItem, MemoryCategory
            import uuid
            if node.intent == IntentType.MEMORY_STORE:
                content = node.arguments.get("content", "")
                mem_item = MemoryItem(
                    id=f"mem-rtr-{uuid.uuid4().hex[:8]}",
                    category=MemoryCategory.NOTES,
                    title=f"User Fact: {content[:40]}",
                    content=content,
                    importance=0.8,
                    confidence=0.9,
                    source="router"
                )
                res = memory_manager.add_memory(mem_item, user_id=user_id)
                return res if isinstance(res, dict) else {"status": "stored", "memory": res}
            elif node.intent == IntentType.MEMORY_QUERY:
                q = node.arguments.get("query", "")
                if any(k in q.lower() for k in ["talking about", "current topic", "working on", "current task", "workspace", "active discussion", "our context", "focus", "current project", "active project"]):
                    from app.presence.workspace import workspace_manager
                    from app.planning.goal_manager import goal_manager
                    topic = workspace_manager.get_item("current_discussion")
                    active_goals = goal_manager.get_active_goals()
                    active_goal = active_goals[0].title if active_goals else None

                    if "task" in q.lower() or "working" in q.lower() or "goal" in q.lower() or "project" in q.lower():
                        summary = f"Currently, you are working on: '{active_goal or topic or 'general assistance'}'."
                    elif topic:
                        summary = f"Currently, our active topic of discussion is: '{topic}'."
                    else:
                        summary = "We are currently in an active conversation session."

                    return {"status": "context_query", "context": True, "summary": summary}



                mems = memory_manager.get_memories(query=q, user_id=user_id)
                if not mems:
                    return {"status": "empty", "query": q, "memories": []}
                return mems




        # 3. AgentManager
        elif node.engine == "AgentManager":
            from app.agents.manager import agent_manager
            goal = node.arguments.get("goal", node.arguments.get("query", ""))
            return await agent_manager.execute_agent_goal(goal, user_id=user_id)

        # 4. VisionManager
        elif node.engine == "VisionManager":
            from app.vision.manager import vision_manager
            return {"status": "ready", "summary": "Vision analysis engine initialized."}

        # 5. HierarchicalPlanner
        elif node.engine == "HierarchicalPlanner":
            from app.planning.planner import hierarchical_planner
            goal_text = node.arguments.get("goal", node.arguments.get("query", ""))
            if node.intent == IntentType.PLAN_QUERY or node.action == "get_plan_status":
                return hierarchical_planner.get_plan_status(goal_text)
            return hierarchical_planner.create_plan(goal_text)


        # 6. Conversational & Wrapper Intents
        msg = node.arguments.get("message", node.arguments.get("query", ""))
        if node.intent in [IntentType.GREETING, IntentType.SOCIAL_CONVERSATION, IntentType.CAPABILITY_QUERY, IntentType.UNKNOWN_INTENT] or node.action in ["greeting", "social_chat", "capability_inquiry"]:
            return {"status": "conversational", "message": msg}

        from app.cognition.manager import cognition_manager
        return await cognition_manager.process_chat(message=msg, user_name=user_id)





subsystem_resolver = SubsystemResolver()
