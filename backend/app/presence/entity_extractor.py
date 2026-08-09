import re
import logging
from typing import Optional, Tuple
from app.presence.schemas import EntityItem

logger = logging.getLogger("harika.presence.entity_extractor")


class EntityExtractor:
    """Converts raw user messages into structured entity models (entity, attribute, value, confidence)."""

    def extract_entity(self, message: str) -> Optional[EntityItem]:
        clean = message.strip()
        lower = clean.lower().rstrip('.!?')

        # Pattern 1: My favourite X is Y / Remember my favourite X is Y / Favourite X is Y
        m_fav = re.search(r'(?:remember\s+)?(?:my\s+)?favour?ite\s+([a-zA-Z0-9_\-]+)\s+is\s+(.+)', lower)
        if m_fav and not lower.startswith("what"):
            item_type = m_fav.group(1).strip().replace(" ", "_")
            val = m_fav.group(2).strip().rstrip('.')
            attr = f"favourite_{item_type}"
            item = EntityItem(
                entity="user",
                attribute=attr,
                value=val,
                confidence=0.98
            )
            logger.info(f"[EntityExtractor] Extracted Entity: entity='{item.entity}', attribute='{item.attribute}', value='{item.value}'.")
            return item

        # Pattern 2: No. Favourite X is Y / No. I like Y now / No, it's Y / No, I meant Y
        m_no = re.search(r'^(?:no[.,\s]+|i\s+(?:like|prefer|meant)\s+|it\'s\s+|it\s+is\s+)(?:favour?ite\s+([a-zA-Z0-9_\-]+)\s+is\s+)?(.+?)(?:\s+now)?$', lower)
        if m_no and not lower.startswith("what") and not lower.startswith("remember"):

            item_type = m_no.group(1).strip().replace(" ", "_") if m_no.group(1) else "preference"
            val = m_no.group(2).strip().rstrip('.')
            attr = f"favourite_{item_type}" if item_type != "preference" else "preference"

            foods = ["biryani", "dosa", "idli", "burger", "pizza", "salad", "rice", "curry", "sushi", "taco", "pasta"]
            drinks = ["coffee", "tea", "water", "juice", "soda", "milk", "beer", "wine"]
            languages = ["python", "java", "c++", "javascript", "typescript", "rust", "go"]
            cities = ["paris", "tokyo", "london", "new york", "berlin"]
            if any(f in val for f in foods):
                attr = "favourite_food"
            elif any(d in val for d in drinks):
                attr = "favourite_drink"
            elif any(l in val for l in languages):
                attr = "favourite_language"
            elif any(c in val for c in cities):
                attr = "favourite_city"



            item = EntityItem(
                entity="user",
                attribute=attr,
                value=val,
                confidence=0.95
            )
            logger.info(f"[EntityExtractor] Extracted Entity: entity='{item.entity}', attribute='{item.attribute}', value='{item.value}'.")
            return item

        # Pattern 3: Query: What is my favourite X? / Do you know my favourite X? / Favourite X? / What do I like drinking/eating?
        m_q = re.search(r'(?:what\s+(?:is|are)\s+(?:my\s+)?favour?ite\s+([a-zA-Z0-9_\-]+)|do\s+you\s+know\s+(?:my\s+)?favour?ite\s+([a-zA-Z0-9_\-]+)|favour?ite\s+([a-zA-Z0-9_\-]+)|what\s+do\s+i\s+like\s+([a-zA-Z0-9_\-]+))', lower)
        if m_q and not lower.startswith("remember"):
            raw_attr = m_q.group(1) or m_q.group(2) or m_q.group(3) or m_q.group(4) or "preference"
            clean_attr = raw_attr.strip()
            if clean_attr in ["beverage", "drinking"]:
                attr = "favourite_drink"
            elif clean_attr in ["food", "eating", "dish"]:
                attr = "favourite_food"
            elif clean_attr != "preference":
                attr = f"favourite_{clean_attr}"
            else:
                attr = "preference"

            item = EntityItem(
                entity="user",
                attribute=attr,
                value="",
                confidence=0.90
            )
            logger.info(f"[EntityExtractor] Extracted Query Entity: entity='{item.entity}', attribute='{item.attribute}'.")
            return item

        # Pattern 3.5: General Attribute Query: What is my X? / What is X?
        m_gen = re.search(r'^what\s+(?:is|are)\s+(?:my\s+)?([a-zA-Z0-9_\-\s]+?)(?:\?|$)', lower)

        if m_gen and not lower.startswith("remember") and not any(k in lower for k in ["talking", "topic", "working"]):
            attr_name = m_gen.group(1).strip().replace(" ", "_")
            if attr_name and attr_name not in ["that", "it", "this"]:
                item = EntityItem(
                    entity="user",
                    attribute=attr_name,
                    value="",
                    confidence=0.90
                )
                logger.info(f"[EntityExtractor] Extracted General Attribute Query Entity: entity='{item.entity}', attribute='{item.attribute}'.")
                return item

        # Pattern 4: Pronoun Resolution Query (What is it? / Do you know it?)

        if lower in ["what is it", "what is that", "do you know it"]:
            from app.presence.workspace import workspace_manager
            last_disc = workspace_manager.get_item("current_discussion") or ""
            attr = "favourite_drink" if "drink" in last_disc or "coffee" in last_disc or "tea" in last_disc else "favourite_food"
            item = EntityItem(
                entity="user",
                attribute=attr,
                value="",
                confidence=0.88
            )
            logger.info(f"[EntityExtractor] Resolved Pronoun Entity: entity='{item.entity}', attribute='{item.attribute}'.")
            return item

        return None




entity_extractor = EntityExtractor()
