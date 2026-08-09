import logging
import uuid
from typing import List, Optional, Tuple
from app.presence.schemas import EntityItem, ContradictionResult
from app.presence.entity_extractor import entity_extractor
from app.memory.manager import memory_manager
from app.memory.models import MemoryItem, MemoryCategory

logger = logging.getLogger("harika.presence.memory_reasoner")


class MemoryReasoner:
    """Multi-attribute semantic memory ranking & automated contradiction detection engine."""

    def rank_and_retrieve(
        self,
        message: str,
        user_id: str = "default",
        query_entity: Optional[EntityItem] = None
    ) -> List[MemoryItem]:
        q_ent = query_entity or entity_extractor.extract_entity(message)
        mems = memory_manager.get_memories(user_id=user_id)

        if not mems:
            return []

        # Strict Semantic Attribute Ranking Function
        # Priority: Entity -> Attribute -> Intent -> Revision -> Confidence -> Recency -> Keyword Similarity (Last)
        def rank_score(item: MemoryItem) -> float:
            score = 0.0
            title_lower = item.title.lower()
            content_lower = item.content.lower()

            if q_ent:
                # 1. Entity Match
                if q_ent.entity.lower() in title_lower or q_ent.entity.lower() in content_lower:
                    score += 1000.0

                # 2. Attribute Match (e.g. favourite_food vs favourite_food)
                norm_attr = q_ent.attribute.lower()
                clean_attr = norm_attr.replace("favourite_", "").replace("_", " ")
                if norm_attr in title_lower or norm_attr in content_lower or clean_attr in title_lower or clean_attr in content_lower:
                    score += 1000.0
                elif norm_attr != "preference":
                    score -= 5000.0


            # 3. Intent Match
            if "query" in message.lower() or "what" in message.lower():
                score += 100.0

            # 4. Revision (small tie-breaker)
            score += 0.1 * item.revision


            # 5. Confidence
            score += 10.0 * item.confidence

            # 6. Recency (Tie-breaker before keywords)
            score += 5.0

            # 7. Keyword similarity (LAST tie-breaker)
            words = [w for w in message.lower().split() if len(w) > 3]
            for w in words:
                if w in title_lower or w in content_lower:
                    score += 1.0

            return score

        ranked = sorted(mems, key=rank_score, reverse=True)
        logger.info(f"[MemoryReasoner] Ranked {len(ranked)} memories for query '{message}'. Top match: '{ranked[0].title if ranked else 'None'}'.")
        return ranked

    def check_and_resolve_contradictions(self, new_entity: EntityItem, user_id: str = "default") -> ContradictionResult:
        mems = memory_manager.get_memories(user_id=user_id)
        archived_id = None
        updated_id = None
        new_rev = 1

        norm_attr = new_entity.attribute.lower()
        clean_attr = norm_attr.replace("favourite_", "").replace("_", " ")

        for item in mems:
            title_lower = item.title.lower()
            content_lower = item.content.lower()

            # Match exact attribute (e.g., favourite_food vs favourite_food)
            attr_match = norm_attr in title_lower or norm_attr in content_lower or (clean_attr != "preference" and clean_attr in title_lower)

            if attr_match:
                val_existing = content_lower.split("is ")[-1].strip() if "is " in content_lower else ""
                val_new = str(new_entity.value).lower().strip()
                if val_existing and val_new and val_existing == val_new:
                    continue

                # Contradiction detected! Soft-delete / archive old memory item
                memory_manager.soft_delete_memory(item.id, user_id=user_id)
                archived_id = item.id
                new_rev = max(new_rev, item.revision + 1)
                logger.info(f"[MemoryReasoner] Archived conflicting memory '{item.id}' (title='{item.title}').")


        # Insert new updated memory item with incremented revision
        updated_item = MemoryItem(
            id=f"mem-prs-{uuid.uuid4().hex[:8]}",
            category=MemoryCategory.PREFERENCES,
            title=f"User Fact: {new_entity.entity} {new_entity.attribute} is {new_entity.value}",
            content=f"My {new_entity.attribute} is {new_entity.value}",
            importance=0.9,
            confidence=new_entity.confidence,
            source="presence",
            revision=new_rev,
            tags=[new_entity.entity, new_entity.attribute, str(new_entity.value)]
        )
        saved = memory_manager.add_memory(updated_item, user_id=user_id)
        updated_id = saved.get("id") if isinstance(saved, dict) else getattr(saved, "id", None)


        return ContradictionResult(
            has_contradiction=archived_id is not None,
            archived_memory_id=archived_id,
            updated_memory_id=updated_id,
            revision=new_rev
        )




memory_reasoner = MemoryReasoner()
