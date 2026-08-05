import uuid
import logging
from typing import Optional
from app.planning.schemas import Reflection
from app.planning.events import planning_event_bus, PlanningEventType

logger = logging.getLogger("harika.planning.reflection")


class ReflectionEngine:
    """Records clean post-response reflections without storing raw chain-of-thought reasoning."""

    def reflect_on_interaction(
        self,
        user_message: str,
        assistant_response: str,
        was_tool_used: bool = False,
        tool_name: Optional[str] = None,
        success: bool = True,
        lessons_learned: Optional[str] = None,
        next_recommendation: Optional[str] = None
    ) -> Reflection:
        reflection_id = f"refl-{uuid.uuid4().hex[:8]}"

        # Clean high-level summary and outcome (strictly free of internal CoT reasoning)
        summary_text = f"Processed directive: '{user_message[:50]}'" if user_message else "Processed user input."
        outcome_text = f"Delivered response via {'tool (' + tool_name + ')' if was_tool_used and tool_name else 'cognition engine'}."
        
        default_lessons = "Interaction completed nominally." if success else "Encountered non-fatal execution warning."
        default_rec = "Maintain active context."

        reflection = Reflection(
            id=reflection_id,
            summary=summary_text,
            outcome=outcome_text,
            success=success,
            confidence=0.92 if success else 0.65,
            lessons_learned=lessons_learned or default_lessons,
            next_recommendation=next_recommendation or default_rec
        )

        planning_event_bus.emit(PlanningEventType.REFLECTION_STORED, reflection.model_dump())
        logger.info(f"[ReflectionEngine] Recorded Reflection {reflection_id} (Success={success})")
        return reflection


reflection_engine = ReflectionEngine()

