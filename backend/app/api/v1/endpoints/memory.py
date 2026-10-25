import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.memory.models import MemoryItem, MemoryCategory, MemoryMetrics
from app.memory.manager import memory_manager
from pydantic import BaseModel, Field

router = APIRouter()


class CreateMemoryPayload(BaseModel):
    category: MemoryCategory = Field(default=MemoryCategory.PREFERENCES)
    title: str = Field(..., example="Favorite Programming Language")
    content: str = Field(..., example="Python")
    importance: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)


class UpdateMemoryPayload(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


@router.get("", response_model=List[MemoryItem])
async def list_memories(
    query: Optional[str] = None,
    category: Optional[MemoryCategory] = None
):
    """Retrieves stored memories matching category or search query."""
    return memory_manager.get_memories(query=query or "", category=category, user_id="default")


@router.get("/metrics", response_model=MemoryMetrics)
async def get_memory_metrics():
    """Returns internal Cognitive Memory Engine health statistics and metrics."""
    return memory_manager.get_health_metrics(user_id="default")


@router.post("", response_model=MemoryItem)
async def create_memory(payload: CreateMemoryPayload):
    """Creates or updates a persistent memory item."""
    item = MemoryItem(
        id=f"mem-{uuid.uuid4().hex[:8]}",
        category=payload.category,
        title=payload.title.strip(),
        content=payload.content.strip(),
        importance=payload.importance,
        confidence=payload.confidence,
        source="user_api",
        tags=payload.tags,
    )
    return memory_manager.add_memory(item, user_id="default")


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Applies soft delete to a memory item."""
    success = memory_manager.soft_delete_memory(memory_id, user_id="default")
    if not success:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return {"status": "success", "message": f"Soft-deleted memory item {memory_id}"}


@router.delete("")
async def clear_memories():
    """Clears all stored memory categories for default user."""
    memory_manager.clear_all_memories(user_id="default")
    return {"status": "success", "message": "Cleared all stored memories."}


# ------------------------------------------------------------- Settings > Memory

class MemorySettingsPayload(BaseModel):
    remember_conversations: Optional[bool] = None
    notice_habits: Optional[bool] = None
    learn_listening: Optional[bool] = None


def _overview() -> dict:
    from app.memory.journal import journal, RETENTION_DAYS
    from app.memory.patterns import habits

    items = memory_manager.get_memories(user_id=journal.owner())
    days = journal.days()
    return {
        "settings": journal.settings(),
        "retention_days": RETENTION_DAYS,
        "journal_days": len(days),
        "journal_since": days[0].isoformat() if days else None,
        "facts": [m.model_dump() for m in items if m.category != MemoryCategory.EPISODES],
        "days": sorted((m.model_dump() for m in items if m.category == MemoryCategory.EPISODES),
                       key=lambda m: m["id"], reverse=True),
        "habits": habits.visible(),
        "listening": _listening(),
    }


def _listening() -> dict:
    from app.memory.listening import listening_log
    profile = listening_log.profile()
    return {"learn": listening_log.learning(), "plays": profile["plays"], "hours": profile["hours"],
            "top_artists": profile["top_artists"][:5]}


@router.get("/overview")
async def memory_overview():
    """Everything HARIKA remembers, for Settings > Memory."""
    return _overview()


@router.put("/settings")
async def update_memory_settings(payload: MemorySettingsPayload):
    from app.memory.journal import journal
    from app.memory.listening import listening_log
    changes = payload.model_dump()
    learn = changes.pop("learn_listening")
    if learn is not None:
        listening_log.set_learning(learn)
    journal.update_settings(**changes)
    return _overview()


@router.post("/forget-listening")
async def forget_listening():
    """Forgets what HARIKA learned about the music and videos played on this computer."""
    from app.memory.listening import listening_log
    listening_log.forget()
    return _overview()


@router.delete("/item/{memory_id}")
async def forget_memory(memory_id: str):
    """Removes one memory for good."""
    from app.memory.journal import journal
    if not memory_manager.forget_memory(memory_id, user_id=journal.owner()):
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return _overview()


@router.delete("/habits/{habit_id:path}")
async def dismiss_habit(habit_id: str):
    from app.memory.patterns import habits
    habits.dismiss(habit_id)
    return _overview()


@router.post("/forget-everything")
async def forget_everything():
    """Erases the journal, day summaries, learned facts and habits. Settings stay as they are."""
    from app.memory.digest import digester
    from app.memory.journal import journal
    from app.memory.patterns import habits

    for user in {journal.owner(), "default"}:
        memory_manager.clear_all_memories(user_id=user)
    journal.wipe()
    digester.state_path.unlink(missing_ok=True)
    habits.forget()
    from app.memory.listening import listening_log
    listening_log.forget()
    return _overview()
