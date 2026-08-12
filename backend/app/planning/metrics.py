from typing import List, Dict, Any, Optional
from app.planning.schemas import PlanningMetrics
from app.planning.history import plan_history, PlanHistory


class PlanningMetricsManager:
    """Tracks planning performance, strategy metrics, and clarification rates."""

    def __init__(self, history: Optional[PlanHistory] = None):
        self.history = history or plan_history

    def get_metrics(self) -> PlanningMetrics:
        records = self.history.get_history(limit=100)
        total_plans = len(records)

        if total_plans == 0:
            return PlanningMetrics(
                total_plans=0,
                executed_plans=0,
                success_rate=100.0,
                average_planning_latency_ms=0.0,
                clarification_rate=0.0,
                tool_usage_rate=0.0
            )

        executed = sum(1 for r in records if r.get("state") in ["COMPLETED", "EXECUTING"])
        successes = sum(1 for r in records if r.get("state") == "COMPLETED" or r.get("success", True))
        success_rate = round((successes / total_plans) * 100, 1)

        clarifications = sum(1 for r in records if r.get("decision_strategy") == "ASK_CLARIFICATION")
        clarification_rate = round((clarifications / total_plans) * 100, 1)

        tool_uses = sum(1 for r in records if r.get("was_tool_used", False))
        tool_usage_rate = round((tool_uses / total_plans) * 100, 1)

        total_lat = sum(r.get("planning_latency_ms", 5.0) for r in records)
        avg_lat = round(total_lat / total_plans, 2)

        return PlanningMetrics(
            total_plans=total_plans,
            executed_plans=executed,
            success_rate=success_rate,
            average_planning_latency_ms=avg_lat,
            clarification_rate=clarification_rate,
            tool_usage_rate=tool_usage_rate
        )


planning_metrics_manager = PlanningMetricsManager()
