import uuid
import time
import logging
from typing import Dict, Any, Optional
from app.presence.schemas import ConversationState, PresenceResult, AttentionLevel
from app.presence.workspace import workspace_manager
from app.presence.attention import attention_model
from app.presence.entity_extractor import entity_extractor
from app.presence.context_awareness import context_awareness_engine
from app.presence.goal_inference import goal_inference_engine
from app.presence.memory_reasoner import memory_reasoner
from app.presence.reflection import reflection_engine
from app.presence.verification import verification_engine
from app.presence.experience import experience_engine
from app.presence.initiative import initiative_engine
from app.presence.communication import communication_layer
from app.presence.presence_score import presence_score_calculator
from app.presence.presence_loop import presence_loop
from app.presence.events import presence_event_bus, PresenceEventType
from app.presence.metrics import presence_metrics_manager

logger = logging.getLogger("harika.presence.manager")


class PresenceManager:
    """Stateful Presence Facade Manager representing HARIKA's ongoing awareness (HARIKA v1.1)."""

    def __init__(self):
        self.state = ConversationState()
        self.workspace = workspace_manager
        self.score_calc = presence_score_calculator
        self.loop = presence_loop
        self.loop.start_loop()

    async def process_directive(
        self,
        intent: str,
        engine_name: str,
        raw_message: str,
        subsystem_executor_fn,
        user_id: str = "default"
    ) -> PresenceResult:
        t_start = time.time()
        presence_id = f"prs-{uuid.uuid4().hex[:8]}"

        # 1. Update Working Memory & Attention
        clean_msg = raw_message.lower().strip()
        is_context_query = any(k in clean_msg for k in ["talking about", "current topic", "active discussion", "working on", "current task", "our context", "what is our goal", "what's our goal"])
        if not is_context_query:
            self.workspace.set_item("current_discussion", raw_message)

        att_state = attention_model.evaluate_attention(raw_message, active_agent_id=self.state.current_goal)
        presence_event_bus.emit(PresenceEventType.ATTENTION_CHANGED, {"level": att_state.level})

        # 2. Entity Extraction for State Tracking
        entity_item = entity_extractor.extract_entity(raw_message)
        if entity_item:
            self.state.recent_entities.append(entity_item)
            self.state.current_topic = entity_item.attribute.replace("_", " ").title()

        # 3. Subsystem Execution Delegation
        sub_res = await subsystem_executor_fn()
        self.last_sub_res = sub_res


        # 4. Reflection & Verification
        refl = reflection_engine.reflect_on_execution(intent, sub_res, raw_message)
        presence_event_bus.emit(PresenceEventType.REFLECTION_COMPLETED, {"valid": refl.answered_user_question})

        verif = verification_engine.verify_output(engine_name, sub_res)
        presence_event_bus.emit(PresenceEventType.VERIFICATION_COMPLETED, {"valid": verif.overall_valid})



        # 5. Experience Evaluation (AFTER verification, BEFORE communication)
        exp_dec = experience_engine.evaluate_experience(verif, raw_message, recent_failures=self.state.recent_failures)
        if exp_dec.decision == "offer_diagnostics":
            self.state.recent_failures.clear()  # Reset after offering diagnostics


        # 6. Communication Layer Natural Language Formatting
        natural_text = communication_layer.format_human_response(intent, sub_res, raw_message, experience=exp_dec)

        # 7. Goal Inference & Initiative Evaluation
        goal_inf = goal_inference_engine.infer_goal(raw_message)
        if goal_inf:
            self.state.current_topic = goal_inf.inferred_goal
            presence_event_bus.emit(PresenceEventType.GOAL_INFERRED, {"goal": goal_inf.inferred_goal})

        elapsed_ms = round((time.time() - t_start) * 1000, 2)
        presence_metrics_manager.record_observation(
            reflection_passed=refl.answered_user_question,
            verification_passed=verif.overall_valid,
            latency_ms=elapsed_ms
        )

        return PresenceResult(
            presence_id=presence_id,
            natural_response=natural_text,
            structured_output=sub_res if isinstance(sub_res, dict) else {"result": str(sub_res)},
            verified=verif.overall_valid,
            attention=att_state.level,
            latency_ms=elapsed_ms
        )

    def get_state(self) -> ConversationState:
        return self.state

    def get_working_memory(self) -> Dict[str, Any]:
        return self.workspace.get_all()

    def get_presence_score(self) -> Dict[str, Any]:
        metrics = presence_metrics_manager.get_metrics()
        score = self.score_calc.calculate_score(
            reflections_passed=metrics.reflections_passed,
            verifications_passed=metrics.verifications_passed,
            total_requests=metrics.total_observations
        )
        return score.model_dump()


presence_manager = PresenceManager()
