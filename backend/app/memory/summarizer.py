from typing import List, Dict


class ConversationSummarizer:
    """Generates structured summaries for older conversation turns to maintain continuity."""

    @staticmethod
    def summarize(messages: List[Dict[str, str]]) -> str:
        if not messages:
            return "No prior context."

        user_topics: List[str] = []
        for msg in messages:
            content = msg.get("content", "").strip()
            if msg.get("role") == "user" and content:
                user_topics.append(content[:40] + ("..." if len(content) > 40 else ""))

        if user_topics:
            topics_summary = ", ".join(user_topics[-3:])
            return f"Recent user discussion topics: {topics_summary}."
        return "Recent interaction completed."


conversation_summarizer = ConversationSummarizer()
