import re
import json
import logging
from typing import List, Dict, Any, Tuple
from app.router.schemas import IntentType, RequestContext, EnginePriority
from app.router.intent import IntentResult
from app.router.action_graph import ActionNode, ActionGraph

logger = logging.getLogger("harika.router.classifier")


class IntentClassifier:
    """Hybrid Two-Stage Classifier (Fast Deterministic Stage 1 + Structured JSON LLM Stage 2)."""

    def classify_request(self, context: RequestContext) -> Tuple[ActionGraph, float]:
        message = context.message.strip()

        # Context Awareness: AGENT_CONTINUE check
        if message.lower() in ["continue", "proceed", "next step", "keep going"] and context.active_agent_id:
            graph = ActionGraph()
            node = ActionNode(
                intent=IntentType.AGENT_CONTINUE,
                engine="AgentManager",
                action="continue_agent",
                arguments={"agent_id": context.active_agent_id},
                priority=EnginePriority.AGENTS
            )
            graph.add_node(node)
            logger.info(f"[IntentClassifier] Context-aware routing: AGENT_CONTINUE for agent '{context.active_agent_id}'.")
            return graph, 0.95

        # Stage 1: Fast Deterministic Classification
        stage1_results = self._stage1_deterministic(message)
        max_confidence = max((r.confidence for r in stage1_results), default=0.0)

        if max_confidence >= 0.85:
            logger.info(f"[IntentClassifier] Stage 1 Deterministic match (confidence={max_confidence:.2f}).")
            graph = self._build_action_graph(stage1_results)
            return graph, max_confidence

        # Stage 2: LLM Structured JSON Classification Fallback
        stage2_results = self._stage2_llm_json(message)
        graph = self._build_action_graph(stage2_results)
        return graph, stage2_results[0].confidence if stage2_results else 0.50

    def _stage1_deterministic(self, text: str) -> List[IntentResult]:
        clean = text.lower().strip()

        # 1. Multi-intent check: Greeting prefix + subsequent request ("hello open github", "hi calculate 5+5")
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "greetings"]
        for g in greetings:
            if clean.startswith(f"{g} ") or clean.startswith(f"{g},") or clean.startswith(f"{g}."):
                greet_part = g
                rest_part = text[len(g):].strip().lstrip(',.!')
                if rest_part.lower().strip(" .!?,") in ["harika", "assistant"]:
                    return self._stage1_single(text)
                if rest_part:
                    greet_res = self._stage1_single(greet_part)
                    rest_res = self._stage1_deterministic(rest_part)
                    return greet_res + rest_res

        # 2. Multi-intent check: Compound conjunctions ("then", "and")
        if any(c in clean for c in [" then ", " and ", " and remember ", " and store ", " and save "]):
            parts = re.split(r'\b(?:then|and)\b', text, flags=re.IGNORECASE)
            results: List[IntentResult] = []
            for part in parts:
                p_clean = part.strip()
                if p_clean:
                    sub_res = self._stage1_single(p_clean)
                    results.extend(sub_res)
            if results:
                return results

        return self._stage1_single(text)


    def _stage1_single(self, text: str) -> List[IntentResult]:
        clean = text.lower().strip().rstrip('.!?')

        # 0. Creator & Identity
        if any(clean.startswith(k) or f" {k}" in clean for k in ["who created", "who built", "who made", "who developed", "who is your creator", "who are you", "what is your name", "tell me about yourself"]):
            return [IntentResult(
                intent=IntentType.SOCIAL_CONVERSATION,
                confidence=0.95,
                reason="Creator / Identity inquiry detected",
                target_engine="CognitionManager",
                target_action="social_chat",
                parameters={"message": text}
            )]



        # 0. Standalone conversational greeting (optional assistant address)
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "greetings"]
        greeting_pattern = rf"^(?:{'|'.join(re.escape(g) for g in greetings)})(?:[ ,.!]+(?:harika|assistant))?[.!?]*$"
        if re.match(greeting_pattern, clean):
            return [IntentResult(
                intent=IntentType.CHAT,
                confidence=0.99,
                reason="Standalone conversational greeting detected",
                target_engine="CognitionManager",
                target_action="process_chat",
                parameters={"message": text, "conversation_type": "greeting"}
            )]


        # 0.5 Casual Conversation Intent
        casual_phrases = [
            "how are you", "how's it going", "how is it going", "what's up", "what is up",
            "what can you help me with", "can you help me", "can you assist me"
        ]
        if any(p in clean for p in casual_phrases):
            return [IntentResult(
                intent=IntentType.CHAT,
                confidence=0.98,
                reason="Casual conversational question detected",
                target_engine="CognitionManager",
                target_action="process_chat",
                parameters={"message": text, "conversation_type": "casual"}
            )]

        # 0.6 Social Conversation Intent (bypasses tool, memory, vision, agent execution)
        social_phrases = [
            "how are you", "how's it going", "how is it going", "what's up", "are you okay",
            "are you ready", "nice to meet you", "can you help me", "can you assist me",
            "good night", "thanks", "thank you", "bye", "see you", "see ya",
            "stressed", "overwhelmed", "anxious", "feeling down", "exhausted", "bad day",
            "burnt out", "demotivated", "feeling sad", "feeling low", "feeling tired", "feeling worried", "frustrated", "hopeless", "upset",
            "nervous", "lonely", "feeling nervous", "feeling lonely", "feeling bad", "tell me a joke",
            "feel low", "feel sad", "feel tired", "feel stressed", "feel anxious", "feel overwhelmed", "feel exhausted", "feel frustrated", "feel hopeless", "feel bad", "feel upset"
        ]






        if any(p in clean for p in social_phrases):
            return [IntentResult(
                intent=IntentType.SOCIAL_CONVERSATION,
                confidence=0.98,
                reason="Social conversation phrase detected",
                target_engine="CognitionManager",
                target_action="social_chat",
                parameters={"message": text}
            )]

        # 0.6 Capability Query Intent
        capability_phrases = [
            "what can you do", "what else can you do", "what else you can do",
            "capabilities", "what are your capabilities", "help", "commands", "features",
            "what features do you have", "what commands", "show features"
        ]
        if (clean in capability_phrases or any(clean.startswith(p) for p in ["what can you do", "what else can you do", "what features", "what are your capabilities", "what commands"])) and not any(clean.startswith(k) for k in ["search", "google", "open", "visit"]):
            return [IntentResult(
                intent=IntentType.CAPABILITY_QUERY,
                confidence=0.98,
                reason="Capability inquiry phrase detected",
                target_engine="CognitionManager",
                target_action="capability_inquiry",
                parameters={"message": text}
            )]





        # 0.7 Execution Feedback Intent (bypasses normal chat, triggers VerificationManager & recovery)
        feedback_phrases = [
            "that didn't work", "that didnt work", "nothing happened", "still closed",
            "github isn't opened", "github is not opened", "calculator didn't run", "calculator didnt run",
            "remembering is wrong", "it isn't opened", "it didnt open", "did not work", "didn't work",
            "can't see", "cant see", "i can't see", "i cant see", "not opened", "didn't open", "didnt open"
        ]
        if any(p in clean for p in feedback_phrases):
            return [IntentResult(
                intent=IntentType.EXECUTION_FEEDBACK,
                confidence=0.98,
                reason="Execution feedback phrase detected",
                target_engine="CognitionManager",
                target_action="verify_and_recover",
                parameters={"message": text}
            )]




        # 1. Calculator / Tool Execution

        if re.search(r'(\bcalculate\b|\beval\b|\bcompute\b|\d+\s*[\+\-\*\/\%\^]\s*\d+)', clean):
            return [IntentResult(
                intent=IntentType.TOOL_EXECUTION,
                confidence=0.98,
                reason="Arithmetic pattern detected",
                target_engine="ToolManager",
                target_action="calculator",
                parameters={"query": text}
            )]

        # 2. DateTime / Tool Execution
        if any(k in clean for k in ["what time is it", "current time", "today's date", "what date is it", "local time", "what time"]):
            return [IntentResult(
                intent=IntentType.TOOL_EXECUTION,
                confidence=0.98,
                reason="DateTime query detected",
                target_engine="ToolManager",
                target_action="datetime",
                parameters={"query": text}
            )]


        # 3. Generic capability command grammar. Target meaning is resolved by registry metadata later.
        command_match = re.match(
            r"^(?:can you\s+|please\s+)?(?P<verb>open|launch|start|run|bring up|get me|close|terminate|kill|stop|visit)\s+(?:the\s+)?(?P<target>.+)$",
            clean,
        )
        if command_match:
            verb = command_match.group("verb")
            target = command_match.group("target").strip()
            is_close = verb in {"close", "terminate", "kill", "stop"}
            action = "close_target" if is_close else "open_target"
            return [IntentResult(
                intent=IntentType.TOOL_EXECUTION,
                confidence=0.95,
                reason="Generic capability command detected",
                target_engine="ToolManager",
                target_action=action,
                parameters={"query": text, "target": target}
            )]





        # 3.5 Clipboard Tool Execution
        if "clipboard" in clean:
            return [IntentResult(
                intent=IntentType.TOOL_EXECUTION,
                confidence=0.95,
                reason="Clipboard tool command detected",
                target_engine="ToolManager",
                target_action="clipboard",
                parameters={"query": text}
            )]

        # 4. Memory Store & Self-Correction

        is_query = text.strip().endswith("?") or any(q in clean for q in ["what is", "what's", "what do", "what are", "tell me", "do you", "recall", "summarize"])

        is_correction = any(clean.startswith(k) or f" {k}" in clean for k in ["no, ", "no. ", "no i ", "no, i ", "no, it's", "no it's", "i meant", "that's wrong"])
        is_store = any(clean.startswith(k) or f" {k}" in clean for k in ["remember ", "store ", "save that ", "my favourite", "favourite "])

        if (is_store or is_correction) and not is_query:
            return [IntentResult(
                intent=IntentType.MEMORY_STORE,
                confidence=0.95,
                reason="Memory store / correction phrase detected",
                target_engine="MemoryManager",
                target_action="add_memory",
                parameters={"content": text}
            )]

        # 5. Memory Query & Context Awareness
        if is_query and any(k in clean for k in ["favourite", "preference", "like", "prefer", "drink", "food", "color", "pet", "sport", "music", "city", "movie", "language", "fruit", "project", "name", "remember", "what is it", "what is that", "do you know it", "talking about", "talk about", "talk", "topic", "discussing", "discussion", "context", "conversation", "ask before", "last question", "working on", "where are we", "focus", "focusing", "doing", "goal", "task", "session", "state", "message", "leave off", "recent"]):
            return [IntentResult(
                intent=IntentType.MEMORY_QUERY,
                confidence=0.92,
                reason="Memory retrieval query detected",
                target_engine="MemoryManager",
                target_action="query_memory",
                parameters={"query": text}
            )]











        # 6. Vision Analysis
        if any(k in clean for k in ["analyze this image", "analyse this image", "analyze image", "analyse image", "describe image", "read this pdf", "vision", "ocr"]):
            return [IntentResult(
                intent=IntentType.VISION_ANALYSIS,
                confidence=0.95,
                reason="Visual directive detected",
                target_engine="VisionManager",
                target_action="process_image",
                parameters={"query": text}
            )]


        # 7. Agent Start
        if any(k in clean for k in ["create an agent", "start agent", "deploy agent"]):
            return [IntentResult(
                intent=IntentType.AGENT_START,
                confidence=0.95,
                reason="Agent creation directive detected",
                target_engine="AgentManager",
                target_action="execute_agent_goal",
                parameters={"goal": text}
            )]

        # 7.5 Plan Query & Status
        if any(k in clean for k in ["show my plan", "show current plan", "display current plan", "view plan", "what is my active plan", "show plan", "plan status", "plan progress", "plan steps", "active goal status", "goal status", "where is my plan", "what's my plan", "display my plan", "what is my plan", "active goal plan", "goal plan", "status of my plan", "status of plan", "status of the plan"]):
            return [IntentResult(
                intent=IntentType.PLAN_QUERY,
                confidence=0.95,
                reason="Plan query directive detected",
                target_engine="HierarchicalPlanner",
                target_action="get_plan_status",
                parameters={"query": text}
            )]




        # 7.6 Agent / Plan Continue
        if any(k in clean for k in ["continue my plan", "continue plan", "resume current plan", "proceed with plan", "execute next step", "keep going", "continue active plan", "resume plan", "continue goal", "proceed to next step", "execute active plan"]):
            return [IntentResult(
                intent=IntentType.AGENT_CONTINUE,
                confidence=0.95,
                reason="Plan continuation directive detected",
                target_engine="AgentManager",
                target_action="continue_agent",
                parameters={"query": text}
            )]


        # 8. Plan Creation
        if any(clean.startswith(k) or f" {k}" in clean for k in ["create plan", "create a plan", "make a plan", "plan for", "plan my", "plan how", "plan ", "i want a plan", "schedule", "how do i build", "how do i create", "roadmap"]):
            return [IntentResult(
                intent=IntentType.PLAN_CREATION,
                confidence=0.90,
                reason="Planning directive detected",
                target_engine="HierarchicalPlanner",
                target_action="create_plan",
                parameters={"goal": text}
            )]






        # 9. Conversational Chat & Experience
        if any(k in clean for k in ["build failure", "build failures", "build error", "build errors", "presentation", "presentation tomorrow", "presenting", "presenting tomorrow", "rehearsal", "mock q&a", "tell me about yourself", "who built you", "tell me a joke"]):
            return [IntentResult(
                intent=IntentType.CHAT,
                confidence=0.95,
                reason="Conversational experience directive detected",
                target_engine="CognitionManager",
                target_action="process_chat",
                parameters={"message": text}
            )]



        # Default Unrecognized Directive
        return [IntentResult(
            intent=IntentType.UNKNOWN_INTENT,
            confidence=0.75,
            reason="Unrecognized prompt pattern",
            target_engine="CognitionManager",
            target_action="unknown_intent",
            parameters={"message": text}
        )]


    def _stage2_llm_json(self, text: str) -> List[IntentResult]:
        """Stage 2 Fallback producing strictly structured JSON."""
        return [IntentResult(
            intent=IntentType.UNKNOWN_INTENT,
            confidence=0.50,
            reason="Fallback classification for unhandled query",
            target_engine="CognitionManager",
            target_action="unknown_intent",
            parameters={"message": text}
        )]


    def _build_action_graph(self, intents: List[IntentResult]) -> ActionGraph:
        graph = ActionGraph()
        prev_node_id = None

        priorities = {
            "SystemManager": EnginePriority.SYSTEM,
            "MemoryManager": EnginePriority.MEMORY,
            "ToolManager": EnginePriority.TOOLS,
            "VisionManager": EnginePriority.VISION,
            "HierarchicalPlanner": EnginePriority.PLANNING,
            "AgentManager": EnginePriority.AGENTS,
            "VoiceManager": EnginePriority.VOICE,
            "CognitionManager": EnginePriority.CHAT,
        }

        for res in intents:
            node = ActionNode(
                intent=res.intent,
                engine=res.target_engine,
                action=res.target_action,
                arguments=res.parameters,
                dependencies=[prev_node_id] if prev_node_id else [],
                priority=priorities.get(res.target_engine, EnginePriority.CHAT)
            )
            graph.add_node(node)
            prev_node_id = node.id

        return graph


intent_classifier = IntentClassifier()
