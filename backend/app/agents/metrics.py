import logging
from typing import Dict, Any, Optional
from app.agents.schemas import AgentMetrics
from app.agents.history import agent_history_manager, AgentHistoryManager

logger = logging.getLogger("harika.agents.metrics")


class AgentMetricsManager:
    """Tracks agent performance, completion stats, retry rates, and execution durations."""

    def __init__(self, history: Optional[AgentHistoryManager] = None):
        self.history = history or agent_history_manager

    def get_metrics(self) -> AgentMetrics:
        records = self.history.get_history(limit=500)
        total = len(records)

        if total == 0:
            return AgentMetrics(
                agents_created=0,
                completed_count=0,
                failed_count=0,
                cancelled_count=0,
                average_duration_s=0.0,
                retry_rate_percent=0.0,
                success_rate_percent=100.0,
                average_tasks_per_agent=0.0
            )

        completed = sum(1 for r in records if "completed" in r.get("result_summary", "").lower() or "success" in r.get("result_summary", "").lower())
        failed = sum(1 for r in records if "failed" in r.get("result_summary", "").lower())
        cancelled = sum(1 for r in records if "cancelled" in r.get("result_summary", "").lower())

        total_dur_ms = sum(r.get("duration_ms", 0.0) for r in records)
        avg_dur_s = round((total_dur_ms / total) / 1000.0, 2)

        total_tasks = sum(r.get("tasks_count", 1) for r in records)
        avg_tasks = round(total_tasks / total, 1)

        success_rate = round((completed / total) * 100.0, 1)

        return AgentMetrics(
            agents_created=total,
            completed_count=completed,
            failed_count=failed,
            cancelled_count=cancelled,
            average_duration_s=avg_dur_s,
            retry_rate_percent=0.0,
            success_rate_percent=success_rate,
            average_tasks_per_agent=avg_tasks
        )


agent_metrics_manager = AgentMetricsManager()
