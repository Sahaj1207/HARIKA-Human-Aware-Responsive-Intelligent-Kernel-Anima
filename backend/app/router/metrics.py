import logging
from typing import Dict, Any, Optional
from app.router.schemas import RouterMetrics
from app.router.history import router_history_manager, RouterHistoryManager

logger = logging.getLogger("harika.router.metrics")


class RouterMetricsManager:
    """Calculates self-learning analytics and telemetry metrics for the Cognitive Router."""

    def __init__(self, history_mgr: Optional[RouterHistoryManager] = None):
        self.history_mgr = history_mgr or router_history_manager

    def get_metrics(self) -> RouterMetrics:
        history = self.history_mgr.get_history(limit=500)
        total = len(history)

        if total == 0:
            return RouterMetrics()

        intent_counts: Dict[str, int] = {}
        total_latency = 0.0
        clarifications = 0
        fallbacks = 0
        tool_execs = 0
        tool_successes = 0
        memory_queries = 0
        memory_hits = 0

        for item in history:
            cand = item.get("chosen_engine", "unknown")
            intent_counts[cand] = intent_counts.get(cand, 0) + 1
            total_latency += item.get("execution_time_ms", 0.0)

            if item.get("reason", "").startswith("Confidence score below threshold"):
                clarifications += 1

            if item.get("fallback_used"):
                fallbacks += 1

            if item.get("chosen_engine") == "ToolManager":
                tool_execs += 1
                if item.get("success"):
                    tool_successes += 1

            if item.get("chosen_engine") == "MemoryManager":
                memory_queries += 1
                if item.get("success"):
                    memory_hits += 1

        avg_latency = round(total_latency / total, 2)
        clarification_rate = round((clarifications / total) * 100, 1)
        fallback_rate = round((fallbacks / total) * 100, 1)
        tool_success_rate = round((tool_successes / tool_execs * 100) if tool_execs > 0 else 100.0, 1)
        memory_hit_rate = round((memory_hits / memory_queries * 100) if memory_queries > 0 else 0.0, 1)

        return RouterMetrics(
            total_requests=total,
            intent_frequencies=intent_counts,
            average_routing_latency_ms=avg_latency,
            routing_accuracy=round(100.0 - fallback_rate, 1),
            clarification_rate=clarification_rate,
            fallback_rate=fallback_rate,
            tool_success_rate=tool_success_rate,
            memory_hit_rate=memory_hit_rate
        )


router_metrics_manager = RouterMetricsManager()
