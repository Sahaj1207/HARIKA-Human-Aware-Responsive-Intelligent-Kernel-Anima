from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    USER_PROFILE = "user_profile"
    PREFERENCES = "preferences"
    PROJECTS = "projects"
    GOALS = "goals"
    SKILLS = "skills"
    RELATIONSHIPS = "relationships"
    EPISODES = "episodes"
    TASKS = "tasks"
    NOTES = "notes"
    SYSTEM = "system"


class MemoryItem(BaseModel):
    """Core Object Model for a Cognitive Memory item."""

    id: str = Field(..., description="Unique memory identifier string")
    category: MemoryCategory = Field(default=MemoryCategory.PREFERENCES, description="Strict memory classification category")
    title: str = Field(..., description="Short descriptive title of the memory")
    content: str = Field(..., description="Factual content payload of the memory")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Evaluated importance score from 0.0 to 1.0")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence rating of the memory fact from 0.0 to 1.0")
    source: str = Field(default="user", description="Origin source of the memory ('user', 'system', 'extractor')")
    tags: List[str] = Field(default_factory=list, description="Associated keyword tags")
    version: int = Field(default=1, description="Major version integer")
    revision: int = Field(default=1, description="Revision update count")
    deleted: bool = Field(default=False, description="Soft delete status flag")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO UTC timestamp of creation")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO UTC timestamp of last update")
    last_accessed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO UTC timestamp of last retrieval")


class MemoryQuery(BaseModel):
    """Search & filter parameters for Memory Retrieval."""

    query: Optional[str] = None
    category: Optional[MemoryCategory] = None
    min_importance: float = 0.0
    limit: int = 10
    include_deleted: bool = False


class MemoryMetrics(BaseModel):
    """Health statistics for the Cognitive Memory Engine."""

    total_memories: int
    categories_count: Dict[str, int]
    deleted_count: int
    average_importance: float
    average_confidence: float
    latest_update: str
    storage_bytes: int
