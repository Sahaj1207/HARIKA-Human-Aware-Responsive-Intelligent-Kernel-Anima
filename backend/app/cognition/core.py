from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from app.cognition.schemas import CognitiveDecision, CognitiveGoal, CognitiveMode

if TYPE_CHECKING:
    from app.router.action_graph import ActionGraph
    from app.router.classifier import IntentClassifier
    from app.router.context import ContextBuilder
    from app.router.schemas import IntentType, RequestContext


_DEFAULT_SEMANTIC = object()


class CognitiveCore:
    """Central reasoning boundary between request context, routing, and execution."""

    def __init__(
        self,
        context_builder_instance: Optional["ContextBuilder"] = None,
        classifier: Optional["IntentClassifier"] = None,
        semantic_interpreter_instance: Any = None,
    ):
        self.context_builder = context_builder_instance
        self.classifier = classifier
        self._semantic_enabled = semantic_interpreter_instance is not None
        self.semantic_interpreter = None if semantic_interpreter_instance is _DEFAULT_SEMANTIC else semantic_interpreter_instance
        self._session_goals: Dict[Tuple[str, str], str] = {}
        self._session_targets: Dict[Tuple[str, str], str] = {}

    def perceive(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> "RequestContext":
        if self.context_builder is None:
            from app.router.context import context_builder
            self.context_builder = context_builder
        return self.context_builder.build_context(
            message=message,
            user_id=user_id,
            session_id=session_id,
            conversation_history=conversation_history,
        )

    def understand(self, context: "RequestContext") -> Tuple["ActionGraph", float]:
        """Classify once and return the normalized action graph."""
        if self.classifier is None:
            from app.router.classifier import intent_classifier
            self.classifier = intent_classifier
        return self.classifier.classify_request(context)

    def _understand_semantically(self, context: "RequestContext"):
        if self.semantic_interpreter is None:
            from app.cognition.semantic.interpreter import default_semantic_interpreter
            self.semantic_interpreter = default_semantic_interpreter()
        request = self.semantic_interpreter.interpret_sync(context.message, context)
        return request, self._action_graph_from_semantic(request, context.message, self.semantic_interpreter.catalog)

    @staticmethod
    def _action_graph_from_semantic(request: Any, message: str, catalog: Any):
        from app.router.action_graph import ActionGraph, ActionNode
        from app.router.schemas import EnginePriority, IntentType

        graph = ActionGraph()
        entry = catalog.get(request.candidate_capabilities[0]) if request.candidate_capabilities else None

        if not request.is_valid or entry is None:
            graph.add_node(ActionNode(
                intent=IntentType.UNKNOWN_INTENT,
                engine="CognitionManager",
                action="process_chat",
                arguments={
                    "message": message,
                    "semantic_request": request.model_dump(),
                },
            ))
            return graph

        intent = IntentType.TOOL_EXECUTION if entry.engine == "ToolManager" else IntentType.UNKNOWN_INTENT
        action = entry.action or request.operation or entry.capability_id
        arguments = dict(request.entities)
        target = arguments.get("target")
        if isinstance(target, dict):
            arguments["target"] = target.get("value")
        if entry.capability_id == "open_application":
            arguments["app_name"] = arguments.get("target")
            arguments["action"] = "close" if request.operation == "close" else "launch"
        arguments["query"] = message
        graph.add_node(ActionNode(
            intent=intent,
            engine=entry.engine or "CognitionManager",
            action=action,
            arguments=arguments,
            priority=EnginePriority.TOOLS if intent is IntentType.TOOL_EXECUTION else EnginePriority.CHAT,
        ))
        return graph

    def cognize(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> CognitiveDecision:
        context = self.perceive(message, user_id, session_id, conversation_history)
        semantic_request = None
        if self._semantic_enabled:
            try:
                semantic_request, action_graph = self._understand_semantically(context)
                confidence = semantic_request.confidence
            except Exception:
                # Compatibility boundary: malformed/unavailable interpretation
                # falls back to the existing classifier, never to execution.
                action_graph, confidence = self.understand(context)
        else:
            action_graph, confidence = self.understand(context)
        from app.router.schemas import IntentType
        from app.tools.capability_resolver import capability_resolver
        for node in action_graph.nodes:
            capability_resolver.normalize_node(node)
        goal = self._infer_goal(context, action_graph, confidence, semantic_request)
        mode, clarification = self._decide(action_graph, goal)

        if action_graph.nodes and goal.probable_goal in {"conversation_or_entertainment", "advice_or_exploration"}:
            primary = action_graph.nodes[0]
            if primary.intent is IntentType.UNKNOWN_INTENT:
                primary.intent = IntentType.CHAT
                primary.engine = "CognitionManager"
                primary.action = "process_chat"

        if action_graph.nodes:
            action_graph.nodes[0].arguments.update({
                "cognitive_goal": goal.probable_goal,
                "desired_outcome": goal.desired_outcome,
                "cognitive_context": goal.context,
            })
            target = action_graph.nodes[0].arguments.get("app_name") or action_graph.nodes[0].arguments.get("target")
            if target:
                self._session_targets[(user_id, session_id)] = target

        if mode is not CognitiveMode.ASK or goal.probable_goal != "understand_user_request":
            self._session_goals[(user_id, session_id)] = goal.probable_goal

        return CognitiveDecision(
            request=message,
            context=context,
            goal=goal,
            mode=mode,
            confidence=confidence,
            action_graph=action_graph,
            clarification_needed=mode is CognitiveMode.ASK,
            clarification_question=clarification,
            rationale=self._rationale(mode, action_graph),
            semantic_request=semantic_request,
        )

    def _infer_goal(
        self,
        context: "RequestContext",
        action_graph: "ActionGraph",
        confidence: float,
        semantic_request: Optional[Any] = None,
    ) -> CognitiveGoal:
        from app.router.schemas import IntentType

        node = action_graph.nodes[0] if action_graph.nodes else None
        intent = node.intent if node else IntentType.UNKNOWN_INTENT
        action = node.action if node else None
        session_key = (context.user_id, context.session_id)
        active_goal = self._session_goals.get(session_key)
        active_target = self._session_targets.get(session_key)
        message = context.message.strip()
        clean = message.lower().rstrip(".!?")

        if semantic_request is not None and semantic_request.probable_goal:
            probable_goal = semantic_request.probable_goal
            goal_context = {"source": "semantic_interpreter"}
        elif active_goal and self._is_contextual_follow_up(message, action_graph):
            probable_goal = clean
            goal_context = {"active_goal": active_goal, "active_target": active_target, "source": "short_term_context"}
        elif any(marker in clean for marker in ("bored", "something to do", "nothing to do")):
            probable_goal = "conversation_or_entertainment"
            goal_context = {"source": "current_message"}
        elif "should i" in clean or "what should i do" in clean or "any ideas" in clean:
            probable_goal = "advice_or_exploration"
            goal_context = {"source": "current_message"}
        elif intent in (IntentType.CHAT, IntentType.GREETING, IntentType.SOCIAL_CONVERSATION, IntentType.CAPABILITY_QUERY):
            probable_goal = "conversation"
            goal_context = {"source": "current_message"}
        elif intent in (IntentType.MEMORY_STORE, IntentType.MEMORY_UPDATE, IntentType.MEMORY_QUERY):
            probable_goal = "memory"
            goal_context = {"source": "current_message"}
        elif intent in (IntentType.PLAN_CREATION, IntentType.PLAN_QUERY):
            probable_goal = "planning"
            goal_context = {"source": "current_message"}
        elif intent in (IntentType.AGENT_START, IntentType.AGENT_CONTINUE, IntentType.AGENT_STATUS):
            probable_goal = "agent_execution"
            goal_context = {"source": "current_message"}
        elif action:
            probable_goal = "complete_capability_action"
            goal_context = {"source": "current_message"}
        else:
            probable_goal = "understand_user_request"
            goal_context = {"source": "current_message"}

        required = list(semantic_request.candidate_capabilities) if semantic_request is not None else ([node.action] if node and node.action else [])
        return CognitiveGoal(
            probable_goal=probable_goal,
            desired_outcome=self._desired_outcome(intent, action),
            confidence=confidence,
            entities=dict(semantic_request.entities) if semantic_request is not None else (dict(node.arguments) if node else {}),
            context=goal_context,
            required_capabilities=required,
        )

    @staticmethod
    def _is_contextual_follow_up(message: str, action_graph: "ActionGraph") -> bool:
        from app.router.schemas import IntentType

        if len(message.split()) > 5 or len(action_graph.nodes) != 1:
            return False
        return action_graph.nodes[0].intent in {
            IntentType.CHAT,
            IntentType.UNKNOWN_INTENT,
            IntentType.SOCIAL_CONVERSATION,
        }

    @staticmethod
    def _desired_outcome(intent: Any, action: Optional[str]) -> str:
        from app.router.schemas import IntentType

        if action:
            return f"Complete the requested {action} capability."
        if intent in (IntentType.MEMORY_STORE, IntentType.MEMORY_UPDATE):
            return "Store or update user information as requested."
        if intent is IntentType.MEMORY_QUERY:
            return "Retrieve the relevant remembered information."
        if intent in (IntentType.PLAN_CREATION, IntentType.PLAN_QUERY):
            return "Create or inspect a plan for the user's goal."
        if intent is IntentType.UNKNOWN_INTENT:
            return "Understand the user's intended outcome before acting."
        return "Provide a useful conversational answer."

    @staticmethod
    def _decide(action_graph: "ActionGraph", goal: CognitiveGoal) -> Tuple[CognitiveMode, Optional[str]]:
        from app.router.schemas import IntentType

        if not action_graph.nodes:
            return CognitiveMode.ASK, "What outcome would you like me to help with?"

        primary = action_graph.nodes[0]
        if goal.probable_goal in {"conversation_or_entertainment", "advice_or_exploration"}:
            return CognitiveMode.ANSWER, None
        if primary.intent is IntentType.UNKNOWN_INTENT:
            return CognitiveMode.ASK, "What outcome would you like me to help with?"
        if primary.action == "close_website":
            return CognitiveMode.REPORT_UNSUPPORTED, None
        if primary.intent in (IntentType.MEMORY_STORE, IntentType.MEMORY_UPDATE):
            return CognitiveMode.REMEMBER, None
        if primary.intent in (IntentType.PLAN_CREATION, IntentType.PLAN_QUERY):
            return CognitiveMode.PLAN, None
        if primary.intent in (IntentType.TOOL_EXECUTION, IntentType.VISION_ANALYSIS, IntentType.AGENT_START, IntentType.AGENT_CONTINUE):
            return CognitiveMode.ACT, None
        return CognitiveMode.ANSWER, None

    @staticmethod
    def _rationale(mode: CognitiveMode, action_graph: "ActionGraph") -> str:
        return f"Cognitive Core selected {mode.value} for {len(action_graph.nodes)} normalized action node(s)."


cognitive_core = CognitiveCore(semantic_interpreter_instance=_DEFAULT_SEMANTIC)
