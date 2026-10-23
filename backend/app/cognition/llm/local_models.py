"""First-run help for on-device models: is Ollama running, which model fits this
computer, and downloading it with progress shown in the app."""
import asyncio
import ctypes
import json
import logging
import platform
import subprocess
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("harika.llm.local")

# Model chosen by available memory: the default needs ~3 GB of RAM while running.
SMALL_MODEL = "qwen2.5:1.5b"
SMALL_MODEL_SIZE = "1 GB"
DEFAULT_MODEL_SIZE = "2.5 GB"


def total_memory_gb() -> Optional[float]:
    try:
        system = platform.system()
        if system == "Windows":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullTotalPhys / 1024 ** 3
        if system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip()) / 1024 ** 3
        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            return int(meminfo.readline().split()[1]) / 1024 ** 2
    except Exception:
        return None


def recommended_model() -> Dict[str, str]:
    memory = total_memory_gb()
    if memory is not None and memory < 8:
        return {"model": SMALL_MODEL, "size": SMALL_MODEL_SIZE, "reason": "fits computers with less memory"}
    return {"model": settings.OLLAMA_MODEL, "size": DEFAULT_MODEL_SIZE, "reason": "has the best balance of speed and quality"}


async def ollama_status() -> Dict[str, Any]:
    recommended = recommended_model()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            reply = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            reply.raise_for_status()
        models = [m["name"] for m in reply.json().get("models", [])]
    except Exception:
        return {"running": False, "models": [], "recommended": recommended, "has_recommended": False}
    return {
        "running": True,
        "models": models,
        "recommended": recommended,
        "has_recommended": recommended["model"] in models,
    }


class ModelDownload:
    """One download at a time; progress is published as live 'model_download' events."""

    def __init__(self):
        self.task: Optional[asyncio.Task] = None

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, model: str) -> bool:
        if self.running:
            return False
        self.task = asyncio.get_running_loop().create_task(self._pull(model))
        return True

    async def _pull(self, model: str) -> None:
        from app.core.live_events import live_events
        from app.cognition.llm.manager import llm_settings

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/pull"
        last_percent = -1
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as client:
                async with client.stream("POST", url, json={"model": model, "stream": True}) as reply:
                    reply.raise_for_status()
                    async for line in reply.aiter_lines():
                        if not line.strip():
                            continue
                        update = json.loads(line)
                        if update.get("error"):
                            raise RuntimeError(update["error"])
                        total, done = update.get("total"), update.get("completed")
                        percent = int(done * 100 / total) if total and done is not None else None
                        if percent is not None and percent == last_percent:
                            continue
                        last_percent = percent if percent is not None else last_percent
                        live_events.publish("model_download", model=model, status=update.get("status", ""), percent=percent)
            # The new model becomes HARIKA's on-device brain for any role using Ollama.
            for role, choice in llm_settings.load().items():
                if choice["service"] == "ollama":
                    llm_settings.set_role(role, "ollama", model)
            live_events.publish("model_download", model=model, status="done", percent=100)
            live_events.publish("llm_settings_changed", service="ollama")
        except Exception as exc:
            logger.warning(f"[LLM] Model download failed: {exc}")
            live_events.publish("model_download", model=model, status="failed", error=str(exc), percent=None)


model_download = ModelDownload()
