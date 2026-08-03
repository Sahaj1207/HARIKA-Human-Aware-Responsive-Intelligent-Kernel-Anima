import re
from typing import Tuple


class ImportanceEngine:
    """Evaluates the importance score (0.0 to 1.0) for candidate memory facts."""

    HIGH_IMPORTANCE_PATTERNS = [
        r"\b(my name is|i am|call me)\b",
        r"\b(my favorite|i love|i prefer|i like)\b",
        r"\b(current project|working on|building|app name)\b",
        r"\b(career goal|my goal|aiming to)\b",
        r"\b(programming language|tech stack|framework|technology)\b",
    ]

    MEDIUM_IMPORTANCE_PATTERNS = [
        r"\b(sprint|milestone|completed|finished)\b",
        r"\b(schedule|reminder|next step)\b",
        r"\b(opinion|think that|feels like)\b",
    ]

    LOW_IMPORTANCE_PATTERNS = [
        r"\b(coffee|weather|today is|hello|hi|thanks|bye|hot|cold)\b",
    ]

    @classmethod
    def evaluate(cls, text: str, category: str = "preferences") -> Tuple[float, float]:
        """
        Evaluates (importance_score, confidence_score) for a text payload.
        """
        clean_text = text.lower().strip()

        # Check low importance pattern triggers
        for pattern in cls.LOW_IMPORTANCE_PATTERNS:
            if re.search(pattern, clean_text):
                return 0.10, 0.50

        # Check high importance pattern triggers
        for pattern in cls.HIGH_IMPORTANCE_PATTERNS:
            if re.search(pattern, clean_text):
                return 0.95, 0.98

        # Check medium importance pattern triggers
        for pattern in cls.MEDIUM_IMPORTANCE_PATTERNS:
            if re.search(pattern, clean_text):
                return 0.65, 0.85

        # Category based default fallback
        if category in ["user_profile", "projects", "goals", "preferences"]:
            return 0.75, 0.90
        elif category in ["episodes", "tasks", "skills"]:
            return 0.60, 0.80

        return 0.40, 0.70


importance_engine = ImportanceEngine()
