import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("harika.presence.presence_loop")


class PresenceObservationLoop:
    """Lightweight deterministic background observation loop maintaining Presence State continuously."""

    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_decision = "observe_only"

    def start_loop(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop())
            logger.info("[PresenceLoop] Started deterministic background observation loop.")
        except RuntimeError:
            pass

    def stop_loop(self) -> None:
        self.is_running = False
        if self._task:
            self._task.cancel()

    async def _run_loop(self) -> None:
        while self.is_running:
            try:
                # Deterministic check
                self.observe_state()
                await asyncio.sleep(15.0)  # Sleep 15s between observation pulses
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[PresenceLoop] Error in observation loop: {e}")
                await asyncio.sleep(5.0)

    def observe_state(self) -> str:
        # Default decision is strictly observe_only
        self.last_decision = "observe_only"
        logger.debug("[PresenceLoop] Observation pulse: observe_only.")
        return self.last_decision


presence_loop = PresenceObservationLoop()
