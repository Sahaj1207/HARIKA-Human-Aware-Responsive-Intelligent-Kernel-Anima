import uuid
from dataclasses import dataclass
import time
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from app.router.schemas import (
    RequestContext, RoutingDecision, PolicyType, IntentType,
    SimulationRequest, SimulationResponse
)
from app.router.context import context_builder, ContextBuilder
from app.router.classifier import intent_classifier, IntentClassifier
from app.router.confidence import confidence_estimator, ConfidenceEstimator
from app.router.policy import policy_engine, PolicyEngine
from app.router.priority import priority_resolver, EnginePriorityResolver
from app.router.resolver import subsystem_resolver, SubsystemResolver
from app.router.formatter import response_formatter, ResponseFormatter
from app.router.events import router_event_bus, RouterEventType
from app.router.history import router_history_manager, RouterHistoryManager
from app.router.metrics import router_metrics_manager, RouterMetricsManager
from app.core.live_events import live_events

if TYPE_CHECKING:
    from app.cognition.core import CognitiveCore

logger = logging.getLogger("harika.router.manager")

CONFIRMATION_TTL_SECONDS = 120.0


@dataclass
class _PendingPlan:
    """An approved-pending action graph waiting for the user's yes/no."""
    graph: Any
    context: Any
    intent: IntentType
    confidence: float
    policy: Any
    question: str
    created_at: float
    # How the tool that proposed this can redo it with a change ("make it shorter").
    revise: Optional[Dict[str, Any]] = None


class RouterManager:
    """Single Public Facade for HARIKA Cognitive Router (HARIKA v1.0)."""

    def __init__(
        self,
        ctx_builder: Optional[ContextBuilder] = None,
        classifier: Optional[IntentClassifier] = None,
        conf_estimator: Optional[ConfidenceEstimator] = None,
        policy_eng: Optional[PolicyEngine] = None,
        pri_resolver: Optional[EnginePriorityResolver] = None,
        sub_resolver: Optional[SubsystemResolver] = None,
        formatter: Optional[ResponseFormatter] = None,
        history: Optional[RouterHistoryManager] = None,
        metrics: Optional[RouterMetricsManager] = None,
        cognitive_core_instance: Optional["CognitiveCore"] = None
    ):
        self.ctx_builder = ctx_builder or context_builder
        self.classifier = classifier or intent_classifier
        self.conf_estimator = conf_estimator or confidence_estimator
        self.policy_eng = policy_eng or policy_engine
        self.pri_resolver = pri_resolver or priority_resolver
        self.sub_resolver = sub_resolver or subsystem_resolver
        self.formatter = formatter or response_formatter
        self.history = history or router_history_manager
        self.metrics = metrics or router_metrics_manager
        if cognitive_core_instance is None:
            from app.cognition.core import cognitive_core as default_cognitive_core
            cognitive_core_instance = default_cognitive_core
        self.cognitive_core = cognitive_core_instance
        self._pending: Dict[tuple, _PendingPlan] = {}

    async def route_request(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        spoken: bool = False,
    ) -> Dict[str, Any]:
        t_start = time.time()
        decision_id = f"dec-{uuid.uuid4().hex[:8]}"

        logger.info(f"\n=========================================================\nREQUEST\nUser Request: {message}\n=========================================================")

        pending = self._take_pending(user_id, session_id)
        if pending is not None:
            verdict = await self.cognitive_core.interpret_confirmation(message, pending.question)
            logger.info(f"Pending confirmation answered: {verdict}")
            if verdict == "confirm":
                for node in pending.graph.nodes:
                    node.confirmed = True
                return await self._execute_graph(
                    pending.graph, pending.context, message, user_id, session_id, pending.intent,
                    pending.confidence, pending.policy, decision_id, t_start,
                )
            if verdict == "decline":
                return {
                    "decision_id": decision_id,
                    "response": "Okay, I won't do that.",
                    "tone": "neutral",
                    "intent": pending.intent.value,
                    "confidence": pending.confidence,
                    "latency_ms": round((time.time() - t_start) * 1000, 2)
                }
            if verdict == "revise" and pending.revise:
                return await self._execute_graph(
                    self._revision_graph(pending.revise, message), pending.context, message, user_id, session_id,
                    pending.intent, pending.confidence, pending.policy, decision_id, t_start,
                )
            # Anything else is a new request; the unanswered action is dropped.

        # Stage 1-2: Cognitive Core perceives context and classifies once.
        understand_kwargs = {"spoken": True} if spoken else {}
        cognitive_decision = await self.cognitive_core.cognize_async(
            message=message,
            user_id=user_id,
            session_id=session_id,
            conversation_history=conversation_history,
            **understand_kwargs,
        )
        ctx = cognitive_decision.context
        graph = cognitive_decision.action_graph
        confidence = cognitive_decision.confidence
        logger.info("Stage 1\nContext Built")
        router_event_bus.emit(RouterEventType.INTENT_DETECTED, {"message": message, "nodes": len(graph.nodes)})
        logger.info("Stage 2\nIntent Classified")

        # Stage 3: Confidence Calculated
        primary_intent = graph.nodes[0].intent if graph.nodes else IntentType.CHAT
        router_event_bus.emit(RouterEventType.CONFIDENCE_CALCULATED, {"confidence": confidence})
        logger.info(f"Stage 3\nConfidence Calculated ({confidence:.2f})")

        should_clarify = cognitive_decision.clarification_needed
        clarify_msg = cognitive_decision.clarification_question or "Cognitive Core requested clarification."
        confidence_clarify, _ = self.conf_estimator.evaluate(confidence, primary_intent)
        if cognitive_decision.mode.value == "ANSWER":
            confidence_clarify = False
        should_clarify = should_clarify or confidence_clarify
        if should_clarify:
            router_event_bus.emit(RouterEventType.CLARIFICATION_REQUESTED, {"message": clarify_msg})
            return {
                "decision_id": decision_id,
                "response": cognitive_decision.clarification_question or "I'm not completely certain what you'd like me to do. Could you please clarify your request?",
                "clarification_needed": True,
                "tone": "neutral",
                "confidence": confidence,
                "intent": primary_intent.value,
                "mode": cognitive_decision.mode.value,
                "latency_ms": round((time.time() - t_start) * 1000, 2)
            }

        # Stage 4: Policy Selected
        policy = self.policy_eng.determine_policy(primary_intent, ctx)
        logger.info(f"Stage 4\nPolicy Selected ({policy.value})")

        # Stage 5: Engine Priority Resolution / Engine Resolved
        graph = self.pri_resolver.resolve_priority(graph)
        logger.info("Stage 5\nEngine Resolved")

        # Stage 5b: Risky actions wait for the user's explicit approval.
        pending_question = self._confirmation_question(graph)
        if pending_question:
            self._pending[(user_id, session_id)] = _PendingPlan(
                graph=graph, context=ctx, intent=primary_intent, confidence=confidence,
                policy=policy, question=pending_question, created_at=time.time(),
            )
            return {
                "decision_id": decision_id,
                "response": pending_question,
                "tone": "neutral",
                "confirmation_needed": True,
                "confidence": confidence,
                "intent": primary_intent.value,
                "latency_ms": round((time.time() - t_start) * 1000, 2)
            }

        return await self._execute_graph(graph, ctx, message, user_id, session_id, primary_intent, confidence, policy, decision_id, t_start)

    async def _execute_graph(self, graph, ctx, message, user_id, session_id, primary_intent, confidence, policy, decision_id, t_start) -> Dict[str, Any]:
        import traceback

        # Stage 6: Sequential Subsystem Execution & Formatting
        router_event_bus.emit(RouterEventType.ENGINE_SELECTED, {"nodes": len(graph.nodes)})
        node_results = []
        fmt_responses: List[str] = []
        formatter_method = "direct"

        from app.presence.manager import presence_manager

        # Nodes run in order. A failed step halts the remaining steps so later
        # actions never run on top of an unmet precondition.
        halted_reason: Optional[str] = None
        total = len(graph.nodes)
        for index, node in enumerate(graph.nodes, 1):
            if halted_reason is not None:
                node.status = "skipped"
                live_events.publish("step", index=index, total=total, status="skipped", label=self._step_label(node))
                continue
            live_events.publish("step", index=index, total=total, status="started", label=self._step_label(node))
            logger.info(f"Stage 6\nManager Invoked ({node.engine})")
            router_event_bus.emit(RouterEventType.ENGINE_STARTED, {"engine": node.engine})
            node_msg = node.arguments.get("message") or node.arguments.get("query") or node.arguments.get("goal") or message

            try:
                prs_res = await presence_manager.process_directive(
                    intent=node.intent.value,
                    engine_name=node.engine,
                    raw_message=node_msg,
                    subsystem_executor_fn=lambda node=node: self.sub_resolver.execute_node(node, user_id=user_id),
                    user_id=user_id
                )
            except Exception as exc:
                err_trace = traceback.format_exc()
                logger.error(f"Execution Failed for node '{node.id}' on engine '{node.engine}': {exc}\nFull Exception Stack Trace:\n{err_trace}")
                if len(graph.nodes) == 1:
                    raise
                node.status = "failed"
                halted_reason = f"Something went wrong while I tried to {self._step_label(node)}"
                router_event_bus.emit(RouterEventType.ENGINE_COMPLETED, {"engine": node.engine, "status": "failed"})
                live_events.publish("step", index=index, total=total, status="failed", label=self._step_label(node))
                continue

            res = prs_res.structured_output
            node.result = res
            step_failed = isinstance(res, dict) and res.get("success") is False
            node.status = "failed" if step_failed else "completed"
            logger.info(f"Stage 7\nExecution Completed ({node.engine})")
            router_event_bus.emit(RouterEventType.ENGINE_COMPLETED, {"engine": node.engine, "status": node.status})
            live_events.publish("step", index=index, total=total, status=node.status, label=self._step_label(node))

            # Stage 8: Formatter / Presence Communication Invoked
            logger.info("Stage 8\nFormatter Invoked (Presence Communication Layer)")
            router_event_bus.emit(RouterEventType.FORMATTER_STARTED, {"engine": node.engine})
            fmt_text = prs_res.natural_response
            formatter_method = "presence_communication"
            if fmt_text and fmt_text.strip():
                fmt_responses.append(fmt_text.strip())
            node_results.append(res)
            if step_failed and len(graph.nodes) > 1:
                halted_reason = ""  # the step's own reply already says what went wrong
            elif not step_failed:
                self._hold_tool_follow_up(res, ctx, message, user_id, session_id, primary_intent, confidence, policy)

        skipped = [n for n in graph.nodes if n.status == "skipped"]
        if halted_reason:
            fmt_responses.append(f"{halted_reason}.")
        if halted_reason is not None and skipped:
            count = f"the remaining {len(skipped)} step" + ("s" if len(skipped) != 1 else "")
            fmt_responses.append(f"So I stopped before {count}.")

        remember_completed = getattr(self.cognitive_core, "remember_completed", None)
        if remember_completed is not None:
            remember_completed(graph, user_id, session_id)

        from app.presence.tone import strip_tags, tone_for
        final_text, chat_tone = strip_tags("\n\n".join(fmt_responses))
        asking = any(isinstance(r, dict) and isinstance(r.get("result"), dict) and r["result"].get("confirmation")
                     for r in node_results)
        tone = tone_for(node_results, chat_tone, asking=asking)
        # A single successful action's result, said in HARIKA's own voice (facts kept exactly).
        if (not asking and chat_tone is None and halted_reason is None and len(graph.nodes) == 1
                and graph.nodes[0].engine == "ToolManager" and tone not in ("apologetic", "neutral")):
            from app.presence.composer import compose
            try:
                final_text = await compose(final_text, message, tone) or final_text
            except Exception as exc:
                logger.warning(f"Rewording skipped: {exc}")
        elapsed_ms = round((time.time() - t_start) * 1000, 2)


        # Stage 9: Response Returned
        logger.info("Stage 9\nResponse Returned")

        # Record Routing Decision Trace
        decision = RoutingDecision(
            decision_id=decision_id,
            request=message,
            context_summary={"active_agent": ctx.active_agent_id, "active_goal": ctx.active_goal_id},
            candidate_engines=[n.engine for n in graph.nodes],
            chosen_engine=graph.nodes[0].engine if graph.nodes else "CognitionManager",
            chosen_action=graph.nodes[0].action if graph.nodes else "process_chat",
            reason=f"Classified as {primary_intent.value} with confidence {confidence:.2f}",
            confidence=confidence,
            policy=policy,
            execution_time_ms=elapsed_ms,
            formatter_used=formatter_method,
            action_graph_nodes=len(graph.nodes)
        )
        self.history.record_decision(decision)
        self._journal(message, final_text, graph, user_id)

        learned = [fact for r in node_results if isinstance(r, dict) for fact in r.get("learned") or []]
        return {
            "decision_id": decision_id,
            "response": final_text.strip(),
            "tone": tone,
            "learned": learned,
            "intent": primary_intent.value,
            "engine": graph.nodes[0].engine if graph.nodes else "CognitionManager",
            "action": graph.nodes[0].action if graph.nodes else "process_chat",
            "confidence": confidence,
            "policy": policy.value,
            "latency_ms": elapsed_ms,
            "formatter_used": formatter_method,
            "provider": "router-v1.0",
            "model": "cognitive-router"
        }


    def _journal(self, message: str, reply: str, graph, user_id: str) -> None:
        """Keep the exchange in the conversation journal (Settings > Memory can switch this off)."""
        from app.memory.journal import journal

        actions = [{"capability": node.action, "operation": node.arguments.get("operation"),
                    "label": self._step_label(node),
                    "target": node.arguments.get("target") if isinstance(node.arguments.get("target"), str) else None,
                    "ok": node.status == "completed"}
                   for node in graph.nodes if node.engine == "ToolManager"]
        try:
            journal.record(user_id, message, reply, actions)
        except OSError as exc:
            logger.warning(f"Journal not written: {exc}")

    def _take_pending(self, user_id: str, session_id: str) -> Optional["_PendingPlan"]:
        pending = self._pending.pop((user_id, session_id), None)
        if pending is None or time.time() - pending.created_at > CONFIRMATION_TTL_SECONDS:
            return None
        return pending

    def _hold_tool_follow_up(self, res, ctx, message, user_id, session_id, intent, confidence, policy) -> None:
        """A tool can propose a follow-up step that needs approval (e.g. sending a draft it just showed).

        The step is held exactly like a router confirmation: "yes" runs it with
        the confirmed flag, anything else drops it. The tool supplies only data;
        the node is built here, so the follow-up still goes through the executor.
        """
        result = res.get("result") if isinstance(res, dict) else None
        follow_up = result.get("confirmation") if isinstance(result, dict) else None
        if not isinstance(follow_up, dict) or not follow_up.get("capability"):
            return
        from app.router.action_graph import ActionGraph, ActionNode

        graph = ActionGraph()
        graph.add_node(ActionNode(
            intent=IntentType.TOOL_EXECUTION,
            engine="ToolManager",
            action=str(follow_up["capability"]),
            arguments={
                "target": follow_up.get("target"),
                "operation": follow_up.get("operation"),
                "query": message,
                # Details of a proposed action (e.g. the event's time) travel with it.
                **({"parameters": dict(follow_up["parameters"])} if isinstance(follow_up.get("parameters"), dict) else {}),
            },
        ))
        revise = follow_up.get("revise")
        self._pending[(user_id, session_id)] = _PendingPlan(
            graph=graph, context=ctx, intent=intent, confidence=confidence, policy=policy,
            question=str(follow_up.get("question") or "Should I go ahead?"), created_at=time.time(),
            revise=revise if isinstance(revise, dict) and revise.get("capability") else None,
        )

    @staticmethod
    def _revision_graph(revise: Dict[str, Any], message: str):
        """Send "make it shorter" back to the tool that made the draft, as an ordinary step."""
        from app.router.action_graph import ActionGraph, ActionNode

        graph = ActionGraph()
        graph.add_node(ActionNode(
            intent=IntentType.TOOL_EXECUTION,
            engine="ToolManager",
            action=str(revise["capability"]),
            arguments={
                "target": revise.get("target"),
                "operation": revise.get("operation"),
                "query": message,
                "parameters": {"instruction": message},
            },
        ))
        return graph

    @staticmethod
    def _step_label(node) -> str:
        """Short present-tense label for progress display ("open chrome", "thinking")."""
        if node.engine != "ToolManager":
            return "thinking"
        from app.tools.manager import tool_manager
        try:
            plan = tool_manager.plan_node(node)
            if plan.actions:
                tool = tool_manager.registry.get_tool(plan.actions[0].tool_name)
                if tool is not None:
                    return tool.describe_action(plan.actions[0].arguments)
        except Exception:
            pass  # progress display must never affect execution
        return node.action or "working"

    def _confirmation_question(self, graph) -> Optional[str]:
        """Ask before any step whose tool marks this call as needing approval."""
        from app.tools.manager import tool_manager

        risky = []
        for node in graph.nodes:
            if node.engine != "ToolManager" or node.confirmed:
                continue
            description = tool_manager.confirmation_for(tool_manager.plan_node(node))
            if description:
                risky.append(description)
        if not risky:
            return None
        return f"Just to confirm, you want me to {' and '.join(risky)}? Should I go ahead?"


    def simulate_request(self, sim_req: SimulationRequest) -> SimulationResponse:
        decision = self.cognitive_core.cognize(sim_req.message, session_id=sim_req.session_id)
        ctx = decision.context
        graph = decision.action_graph
        confidence = decision.confidence
        primary_intent = graph.nodes[0].intent if graph.nodes else IntentType.CHAT
        policy = self.policy_eng.determine_policy(primary_intent, ctx)
        primary_node = graph.nodes[0] if graph.nodes else None

        return SimulationResponse(
            intent=primary_intent,
            confidence=confidence,
            policy=policy,
            engine=primary_node.engine if primary_node else "CognitionManager",
            action=primary_node.action if primary_node else "process_chat",
            will_execute=False,
            reasoning=f"Predicted intent '{primary_intent.value}' with confidence {confidence:.2f} using policy {policy.value}."
        )


router_manager = RouterManager()
