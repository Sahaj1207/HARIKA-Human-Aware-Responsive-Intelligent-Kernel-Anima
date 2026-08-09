import uuid
import time
import logging
from typing import Dict, Any, Optional, List
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

logger = logging.getLogger("harika.router.manager")


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
        metrics: Optional[RouterMetricsManager] = None
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

    async def route_request(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        import traceback
        t_start = time.time()
        decision_id = f"dec-{uuid.uuid4().hex[:8]}"

        logger.info(f"\n=========================================================\nREQUEST\nUser Request: {message}\n=========================================================")

        # Stage 1: Context Built
        ctx = self.ctx_builder.build_context(message, user_id=user_id, session_id=session_id, conversation_history=conversation_history)
        logger.info("Stage 1\nContext Built")

        # Stage 2: Intent Classified
        graph, confidence = self.classifier.classify_request(ctx)
        router_event_bus.emit(RouterEventType.INTENT_DETECTED, {"message": message, "nodes": len(graph.nodes)})
        logger.info("Stage 2\nIntent Classified")

        # Stage 3: Confidence Calculated
        primary_intent = graph.nodes[0].intent if graph.nodes else IntentType.CHAT
        router_event_bus.emit(RouterEventType.CONFIDENCE_CALCULATED, {"confidence": confidence})
        logger.info(f"Stage 3\nConfidence Calculated ({confidence:.2f})")

        should_clarify, clarify_msg = self.conf_estimator.evaluate(confidence, primary_intent)
        if should_clarify:
            router_event_bus.emit(RouterEventType.CLARIFICATION_REQUESTED, {"message": clarify_msg})
            return {
                "decision_id": decision_id,
                "response": "I'm not completely certain what you'd like me to do. Could you please clarify your request?",
                "clarification_needed": True,
                "confidence": confidence,
                "intent": primary_intent.value,
                "latency_ms": round((time.time() - t_start) * 1000, 2)
            }

        # Stage 4: Policy Selected
        policy = self.policy_eng.determine_policy(primary_intent, ctx)
        logger.info(f"Stage 4\nPolicy Selected ({policy.value})")

        # Stage 5: Engine Priority Resolution / Engine Resolved
        graph = self.pri_resolver.resolve_priority(graph)
        logger.info("Stage 5\nEngine Resolved")

        # Stage 6: Sequential Subsystem Execution & Formatting
        router_event_bus.emit(RouterEventType.ENGINE_SELECTED, {"nodes": len(graph.nodes)})
        node_results = []
        fmt_responses: List[str] = []
        formatter_method = "direct"

        for node in graph.nodes:
            logger.info(f"Stage 6\nManager Invoked ({node.engine})")
            router_event_bus.emit(RouterEventType.ENGINE_STARTED, {"engine": node.engine})
            node_msg = node.arguments.get("message") or node.arguments.get("query") or node.arguments.get("goal") or message


            try:
                from app.presence.manager import presence_manager
                prs_res = await presence_manager.process_directive(
                    intent=node.intent.value,
                    engine_name=node.engine,
                    raw_message=node_msg,
                    subsystem_executor_fn=lambda: self.sub_resolver.execute_node(node, user_id=user_id),
                    user_id=user_id
                )
                res = prs_res.structured_output
                node.result = res
                node.status = "completed"
                logger.info(f"Stage 7\nExecution Completed ({node.engine})")
                router_event_bus.emit(RouterEventType.ENGINE_COMPLETED, {"engine": node.engine, "status": "completed"})
            except Exception as exc:
                err_trace = traceback.format_exc()
                logger.error(f"Execution Failed for node '{node.id}' on engine '{node.engine}': {exc}\nFull Exception Stack Trace:\n{err_trace}")
                raise exc

            # Stage 8: Formatter / Presence Communication Invoked
            logger.info("Stage 8\nFormatter Invoked (Presence Communication Layer)")
            router_event_bus.emit(RouterEventType.FORMATTER_STARTED, {"engine": node.engine})
            fmt_text = prs_res.natural_response
            formatter_method = "presence_communication"
            if fmt_text and fmt_text.strip():
                fmt_responses.append(fmt_text.strip())
            node_results.append(res)

        final_text = "\n\n".join(fmt_responses)
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

        return {
            "decision_id": decision_id,
            "response": final_text.strip(),
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


    def simulate_request(self, sim_req: SimulationRequest) -> SimulationResponse:
        ctx = self.ctx_builder.build_context(sim_req.message, session_id=sim_req.session_id)
        graph, confidence = self.classifier.classify_request(ctx)
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
