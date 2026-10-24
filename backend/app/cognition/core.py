import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple, TYPE_CHECKING

from app.cognition.schemas import CognitiveDecision, CognitiveGoal, CognitiveMode

if TYPE_CHECKING:
    from app.router.action_graph import ActionGraph
    from app.router.classifier import IntentClassifier
    from app.router.context import ContextBuilder
    from app.router.schemas import IntentType, RequestContext

logger = logging.getLogger("harika.cognition.core")

_DEFAULT_SEMANTIC = object()
_CONFIDENT = 0.8


class CognitiveCore:
    """Central reasoning boundary between request context, routing, and execution.

    Understanding happens in two stages, like fast and deliberate human thought:
    the deterministic classifier answers immediately when it is confident, and
    the LLM semantic interpreter is consulted only when it is not (unknown
    intent, an unresolved target, a multi-step request, a low score). Whatever
    the interpreter proposes is validated against registered capabilities
    before it can become an action.
    """

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
        self._session_actions: Dict[Tuple[str, str], Deque[str]] = {}
        self._warming = None

    # ------------------------------------------------------------------ stages

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
        """Fast deterministic understanding, normalized against registered capabilities."""
        if self.classifier is None:
            from app.router.classifier import intent_classifier
            self.classifier = intent_classifier
        graph, confidence = self.classifier.classify_request(context)
        from app.tools.capability_resolver import capability_resolver
        for node in graph.nodes:
            capability_resolver.normalize_node(node)
        return graph, confidence

    def needs_deliberation(self, graph: "ActionGraph", confidence: float) -> bool:
        """Whether the fast path is unsure enough to consult the semantic interpreter."""
        from app.router.schemas import IntentType
        from app.tools.capability_resolver import capability_resolver

        if not self._semantic_enabled:
            return False
        if not graph.nodes or len(graph.nodes) > 1 or confidence < _CONFIDENT:
            return True
        return any(
            node.intent is IntentType.UNKNOWN_INTENT
            # Memory questions are spotted from loose word hints ("what's ... like"),
            # so the interpreter confirms them ("what's the weather like" is weather).
            or node.intent is IntentType.MEMORY_QUERY
            # "remember ..." may be about a person ("remember Mom's number is ..."), which belongs
            # with the people the user knows rather than in free-text memory.
            or node.intent is IntentType.MEMORY_STORE
            # Likewise small talk found inside a longer message ("delete the good night routine").
            or (node.intent is IntentType.SOCIAL_CONVERSATION and node.arguments.get("whole_message") is False)
            or not capability_resolver.is_resolved(node)
            # A free-text fallback ("open <anything>" as a file search) is a guess, not understanding.
            or node.arguments.get("resolution_confidence", 1.0) < _CONFIDENT
            for node in graph.nodes
        )

    def _interpreter(self):
        if self.semantic_interpreter is None:
            from app.cognition.semantic.interpreter import default_semantic_interpreter
            self.semantic_interpreter = default_semantic_interpreter()
        return self.semantic_interpreter

    def _hints(self, user_id: str, session_id: str, spoken: bool = False) -> Dict[str, Any]:
        from app.tools.productivity.people_tool import people_store
        from app.tools.productivity.routine_tool import routine_store
        return {"recent_actions": list(self._session_actions.get((user_id, session_id), [])), "spoken": spoken,
                "routines": routine_store.names(), "people": people_store.labels()}

    def _routine_trigger(self, message: str) -> Optional[Any]:
        """The user said a saved routine's own name: run it without asking the model what it means."""
        from app.cognition.semantic.contract import ResolvedStep, SemanticRequest
        from app.tools.productivity.routine_tool import routine_store

        routine = routine_store.match_trigger(message)
        if routine is None:
            return None
        step = ResolvedStep(operation="run_routine", target=routine["name"], capability="run_routine",
                            tool_name="routines", confidence=1.0)
        return SemanticRequest(raw_text=message, probable_goal="run_routine", operation="run_routine",
                               entities={"target": routine["name"]}, candidate_capabilities=["run_routine"],
                               confidence=0.99, steps=[step])

    async def _interpret_async(self, context: "RequestContext", user_id: str, session_id: str, spoken: bool = False):
        interpreter = self._interpreter()
        if hasattr(interpreter, "interpret"):
            return await interpreter.interpret(context.message, context, hints=self._hints(user_id, session_id, spoken))
        return interpreter.interpret_sync(context.message, context)

    def _interpret_sync(self, context: "RequestContext", user_id: str, session_id: str):
        interpreter = self._interpreter()
        try:
            return interpreter.interpret_sync(context.message, context, hints=self._hints(user_id, session_id))
        except TypeError:
            return interpreter.interpret_sync(context.message, context)

    async def warm_up(self) -> None:
        """Load the interpretation model before the first request; a cold load takes ~15s."""
        if not self._semantic_enabled:
            return
        try:
            # Generous limit: on CPU a cold prompt evaluation alone can exceed a minute.
            await self._interpreter().interpret("hello", timeout=240.0)
            logger.info("[CognitiveCore] Semantic interpreter warmed up.")
        except Exception as exc:
            logger.warning(f"[CognitiveCore] Warm-up did not complete: {exc}")

    def _rewarm_in_background(self) -> None:
        """After a timeout, rebuild the model's prompt cache once instead of failing every request."""
        import asyncio
        if self._warming is None or self._warming.done():
            self._warming = asyncio.get_running_loop().create_task(self.warm_up())

    async def interpret_confirmation(self, reply: str, question: str) -> str:
        """'confirm', 'decline' or 'other' for a reply to a pending yes/no question.

        Bare yes/no is answered immediately; anything else is judged by the
        interpreter. If the interpreter is unavailable the answer is 'other', so a
        risky action is never run on an uncertain reading.
        """
        bare = reply.strip().lower().strip(".!?")
        if bare in {"yes", "y"}:
            return "confirm"
        if bare in {"no", "n"}:
            return "decline"
        if not self._semantic_enabled:
            return "other"
        try:
            return await self._interpreter().interpret_confirmation(reply, question)
        except Exception as exc:
            logger.warning(f"[CognitiveCore] Could not interpret confirmation reply: {exc}")
            return "other"

    # --------------------------------------------------------------- decisions

    async def cognize_async(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        spoken: bool = False,
    ) -> CognitiveDecision:
        """Preferred entry point for async callers; never blocks the event loop on the LLM.

        spoken: the message came from speech recognition and may contain misheard words.
        """
        context = self.perceive(message, user_id, session_id, conversation_history)
        graph, confidence = self.understand(context)
        semantic_request = self._routine_trigger(message)
        if semantic_request is not None:
            graph = type(graph)()  # the user's own routine name replaces any keyword guess ("good night" small talk)
        semantic_failure = None
        if semantic_request is None and self.needs_deliberation(graph, confidence):
            try:
                semantic_request = await self._interpret_async(context, user_id, session_id, spoken)
            except Exception as exc:
                # Malformed/unavailable interpretation keeps the fast-path result, never executes.
                logger.warning(f"[CognitiveCore] Semantic interpretation unavailable: {exc}")
                from app.cognition.semantic.interpreter import SemanticTimeoutError
                if isinstance(exc, SemanticTimeoutError):
                    semantic_failure = "timeout"
                    self._rewarm_in_background()
        return self._conclude(context, graph, confidence, semantic_request, user_id, session_id, semantic_failure)

    def cognize(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> CognitiveDecision:
        context = self.perceive(message, user_id, session_id, conversation_history)
        graph, confidence = self.understand(context)
        semantic_request = self._routine_trigger(message)
        if semantic_request is not None:
            graph = type(graph)()  # the user's own routine name replaces any keyword guess ("good night" small talk)
        if semantic_request is None and self.needs_deliberation(graph, confidence):
            try:
                semantic_request = self._interpret_sync(context, user_id, session_id)
            except Exception as exc:
                logger.warning(f"[CognitiveCore] Semantic interpretation unavailable: {exc}")
        return self._conclude(context, graph, confidence, semantic_request, user_id, session_id)

    def _conclude(
        self,
        context: "RequestContext",
        graph: "ActionGraph",
        confidence: float,
        semantic_request: Optional[Any],
        user_id: str,
        session_id: str,
        semantic_failure: Optional[str] = None,
    ) -> CognitiveDecision:
        from app.router.schemas import IntentType

        graph, confidence = self._merge(graph, confidence, semantic_request, context.message)
        goal = self._infer_goal(context, graph, confidence, semantic_request)
        mode, clarification = self._decide(graph, goal, semantic_request)
        if mode is CognitiveMode.ASK and semantic_failure == "timeout":
            from app.cognition.llm.manager import RoleProvider
            clarification = (
                "My language model is still loading, so I couldn't fully understand that. Give me a moment and try again."
                if RoleProvider("understanding").is_local() else
                # A cloud service is never "loading": it's busy (a free tier's per-minute limit).
                "I'm getting a lot of requests through right now, so I couldn't think that through. "
                "Give me a few seconds and ask again."
            )

        if graph.nodes and goal.probable_goal in {"conversation_or_entertainment", "advice_or_exploration"}:
            primary = graph.nodes[0]
            if primary.intent is IntentType.UNKNOWN_INTENT:
                self._as_conversation(primary, context.message)

        if graph.nodes:
            graph.nodes[0].arguments.update({
                "cognitive_goal": goal.probable_goal,
                "desired_outcome": goal.desired_outcome,
                "cognitive_context": goal.context,
            })
        if mode is not CognitiveMode.ASK or goal.probable_goal != "understand_user_request":
            self._session_goals[(user_id, session_id)] = goal.probable_goal

        return CognitiveDecision(
            request=context.message,
            context=context,
            goal=goal,
            mode=mode,
            confidence=confidence,
            action_graph=graph,
            clarification_needed=mode is CognitiveMode.ASK,
            clarification_question=clarification,
            rationale=self._rationale(mode, graph, semantic_request),
            semantic_request=semantic_request,
        )

    def _merge(self, graph: "ActionGraph", confidence: float, semantic_request: Optional[Any], message: str):
        """Combine fast-path and semantic understanding into one action graph."""
        from app.router.schemas import IntentType
        from app.tools.capability_resolver import capability_resolver

        if semantic_request is None:
            # Without a semantic judgement, unknown fragments beside a confident intent
            # ("hi" + "there") are residue of splitting, not separate requests.
            known = [n for n in graph.nodes if n.intent is not IntentType.UNKNOWN_INTENT]
            if known and len(known) < len(graph.nodes):
                graph.nodes = known
            return graph, confidence

        if getattr(semantic_request, "is_conversational", False):
            # The interpreter judged this to be conversation, not a command: keep any
            # confident non-tool understanding (memory, planning...) and answer the rest.
            # A greeting that opens a longer message ("hi, I love dosa") is part of the
            # conversation, not a separate reply that would drop the rest.
            def opener(node) -> bool:
                return len(graph.nodes) > 1 and (
                    node.intent in (IntentType.GREETING, IntentType.SOCIAL_CONVERSATION)
                    or node.arguments.get("conversation_type") == "greeting")

            kept = [
                n for n in graph.nodes
                if n.intent is not IntentType.UNKNOWN_INTENT and not opener(n)
                and capability_resolver.is_resolved(n)
            ]
            graph.nodes = kept or graph.nodes[:1]
            if not kept and graph.nodes:
                self._as_conversation(graph.nodes[0], message)
            elif not graph.nodes:
                from app.router.action_graph import ActionNode
                graph.add_node(ActionNode(intent=IntentType.CHAT, engine="CognitionManager", action="process_chat", arguments={"message": message}))
            return graph, max(confidence, semantic_request.confidence)

        if semantic_request.is_valid:
            semantic_graph = self._action_graph_from_semantic(semantic_request, message, self._interpreter().catalog)
            # Preserve confident fast-path intents the interpreter does not model
            # ("calculate ... and remember it"): memory, planning, calculator, etc.
            for node in graph.nodes:
                # Small talk spotted from words like "good night" is residue once the
                # interpreter found a real request ("when I say good night, ...").
                if node.intent in (IntentType.UNKNOWN_INTENT, IntentType.CHAT, IntentType.MEMORY_QUERY,
                                   IntentType.GREETING, IntentType.SOCIAL_CONVERSATION) \
                        or not capability_resolver.is_resolved(node):
                    continue
                if node.engine == "ToolManager" and capability_resolver.is_semantic_capability(node.action):
                    continue
                if node.intent is IntentType.MEMORY_STORE and any(n.action == "save_person" for n in semantic_graph.nodes):
                    continue  # facts about a person are kept by the people tool instead
                semantic_graph.add_node(node)
            return semantic_graph, semantic_request.confidence

        return graph, confidence

    @staticmethod
    def _as_conversation(node: Any, message: str) -> None:
        from app.router.schemas import IntentType

        node.intent = IntentType.CHAT
        node.engine = "CognitionManager"
        node.action = "process_chat"
        # The whole message is the conversation, not the fragment this node was split from.
        node.arguments = {**node.arguments, "message": message}
        node.arguments.pop("conversation_type", None)

    @staticmethod
    def _action_graph_from_semantic(request: Any, message: str, catalog: Any):
        from app.router.action_graph import ActionGraph, ActionNode
        from app.router.schemas import EnginePriority, IntentType
        from app.tools.capability_resolver import CapabilityResolution, capability_resolver

        graph = ActionGraph()
        steps = list(getattr(request, "steps", []) or [])
        if not steps:
            # Single-intent request without resolved steps (legacy interpreters).
            entry = catalog.get(request.candidate_capabilities[0]) if request.candidate_capabilities else None
            if not request.is_valid or entry is None:
                graph.add_node(ActionNode(
                    intent=IntentType.UNKNOWN_INTENT,
                    engine="CognitionManager",
                    action="process_chat",
                    arguments={"message": message, "semantic_request": request.model_dump()},
                ))
                return graph
            arguments = dict(request.entities)
            target = arguments.get("target")
            if isinstance(target, dict):
                arguments["target"] = target.get("value")
            if entry.capability_id == "open_application":
                arguments["app_name"] = arguments.get("target")
                arguments["action"] = "close" if request.operation == "close" else "launch"
            arguments["query"] = message
            intent = IntentType.TOOL_EXECUTION if entry.engine == "ToolManager" else IntentType.UNKNOWN_INTENT
            graph.add_node(ActionNode(
                intent=intent,
                engine=entry.engine or "CognitionManager",
                action=entry.action or request.operation or entry.capability_id,
                arguments=arguments,
                priority=EnginePriority.TOOLS if intent is IntentType.TOOL_EXECUTION else EnginePriority.CHAT,
            ))
            return graph

        previous_id = None
        for step in CognitiveCore._expand_routines(steps):
            node = ActionNode(
                intent=IntentType.TOOL_EXECUTION,
                engine="ToolManager",
                action=step.capability,
                arguments={"query": message},
                priority=EnginePriority.TOOLS,
                dependencies=[previous_id] if previous_id else [],
            )
            capability_resolver.apply_to_node(
                node,
                CapabilityResolution(
                    capability=step.capability,
                    action=step.operation,
                    target=step.target,
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                ),
                step.operation,
                extra={"parameters": step.parameters} if step.parameters else None,
            )
            graph.add_node(node)
            previous_id = node.id
        return graph

    @staticmethod
    def _expand_routines(steps: List[Any]) -> List[Any]:
        """A run_routine step becomes the routine's own steps, re-resolved against today's capabilities.

        The steps then run like any multi-step request: permissions, confirmation of risky
        steps, progress, verification and halting on failure all apply unchanged.
        """
        from app.cognition.semantic.contract import ResolvedStep
        from app.tools.capability_resolver import capability_resolver
        from app.tools.productivity.routine_tool import routine_store

        expanded: List[Any] = []
        for step in steps:
            routine = routine_store.best_match(step.target or "") if step.capability == "run_routine" else None
            if routine is None:
                expanded.append(step)  # not a routine (or an unknown one, which the tool explains)
                continue
            for saved in routine["steps"]:
                resolution = capability_resolver.resolve_operation(saved["operation"], saved.get("target") or "")
                if not resolution.supported:
                    logger.warning(f"[CognitiveCore] Routine '{routine['name']}' step '{saved.get('label')}' is no longer available.")
                    continue
                expanded.append(ResolvedStep(
                    operation=saved["operation"], target=resolution.target, parameters=dict(saved.get("parameters") or {}),
                    capability=resolution.capability, tool_name=resolution.tool_name,
                    arguments=dict(resolution.arguments), confidence=resolution.confidence,
                ))
        return expanded

    def remember_completed(self, graph: "ActionGraph", user_id: str, session_id: str) -> None:
        """Record actions that actually succeeded, so "close it" refers to something real."""
        key = (user_id, session_id)
        recent = self._session_actions.setdefault(key, deque(maxlen=5))
        for node in graph.nodes:
            if node.engine != "ToolManager" or node.status != "completed":
                continue
            target = node.arguments.get("app_name") or node.arguments.get("target")
            if target:
                verb = node.arguments.get("operation") or node.arguments.get("action") or node.action
                recent.append(f"{verb} {target}")
                self._session_targets[key] = target

    # ------------------------------------------------------------- reasoning

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
        semantic_used = semantic_request is not None and (semantic_request.is_valid or semantic_request.is_conversational)

        if semantic_used and semantic_request.is_valid and semantic_request.probable_goal:
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
            goal_context = {"source": "semantic_interpreter" if semantic_used else "current_message"}
        elif intent in (IntentType.MEMORY_STORE, IntentType.MEMORY_UPDATE, IntentType.MEMORY_QUERY):
            probable_goal = "memory"
            goal_context = {"source": "current_message"}
        elif intent in (IntentType.PLAN_CREATION, IntentType.PLAN_QUERY):
            probable_goal = "planning"
            goal_context = {"source": "current_message"}
        elif intent in (IntentType.AGENT_START, IntentType.AGENT_CONTINUE, IntentType.AGENT_STATUS):
            probable_goal = "agent_execution"
            goal_context = {"source": "current_message"}
        elif action and intent is not IntentType.UNKNOWN_INTENT:
            probable_goal = "complete_capability_action"
            goal_context = {"source": "current_message"}
        else:
            probable_goal = "understand_user_request"
            goal_context = {"source": "current_message"}

        if semantic_request is not None and semantic_request.is_valid:
            required = list(semantic_request.candidate_capabilities)
            entities = dict(semantic_request.entities)
        else:
            required = [n.action for n in action_graph.nodes if n.action]
            entities = dict(node.arguments) if node else {}
        return CognitiveGoal(
            probable_goal=probable_goal,
            desired_outcome=self._desired_outcome(intent, action),
            confidence=confidence,
            entities=entities,
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

        if intent is IntentType.UNKNOWN_INTENT:
            return "Understand the user's intended outcome before acting."
        if action and intent is IntentType.TOOL_EXECUTION:
            return f"Complete the requested {action} capability."
        if intent in (IntentType.MEMORY_STORE, IntentType.MEMORY_UPDATE):
            return "Store or update user information as requested."
        if intent is IntentType.MEMORY_QUERY:
            return "Retrieve the relevant remembered information."
        if intent in (IntentType.PLAN_CREATION, IntentType.PLAN_QUERY):
            return "Create or inspect a plan for the user's goal."
        if action and action != "process_chat":
            return f"Complete the requested {action} capability."
        return "Provide a useful conversational answer."

    @staticmethod
    def _decide(
        action_graph: "ActionGraph",
        goal: CognitiveGoal,
        semantic_request: Optional[Any] = None,
    ) -> Tuple[CognitiveMode, Optional[str]]:
        from app.router.schemas import IntentType
        from app.tools.capability_resolver import capability_resolver

        if not action_graph.nodes:
            return CognitiveMode.ASK, "What outcome would you like me to help with?"

        primary = action_graph.nodes[0]
        if goal.probable_goal in {"conversation_or_entertainment", "advice_or_exploration"}:
            return CognitiveMode.ANSWER, None
        unresolved = [
            n for n in action_graph.nodes
            if n.intent is IntentType.UNKNOWN_INTENT or not capability_resolver.is_resolved(n)
        ]
        if unresolved:
            # Prefer the interpreter's specific explanation over a generic question.
            specific = getattr(semantic_request, "clarification_question", None) if semantic_request is not None else None
            return CognitiveMode.ASK, specific or "What outcome would you like me to help with?"
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
    def _rationale(mode: CognitiveMode, action_graph: "ActionGraph", semantic_request: Optional[Any] = None) -> str:
        source = "semantic interpretation" if semantic_request is not None else "fast-path understanding"
        return f"Cognitive Core selected {mode.value} for {len(action_graph.nodes)} normalized action node(s) via {source}."


cognitive_core = CognitiveCore(semantic_interpreter_instance=_DEFAULT_SEMANTIC)
