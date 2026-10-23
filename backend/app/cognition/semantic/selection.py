"""Which of HARIKA's abilities a message is about, so the language model is shown the right ones.

Cloud models get a short prompt (free tiers count every token): a one-line menu of
every ability, plus full instructions and examples for the few that fit the message.
Choosing those few is this module's job, and it chooses by meaning:

- Each ability is a group: its description plus the example requests that use it.
  Requests that are just conversation form a group of their own.
- With the meaning model (see embedder.py), a message is compared with every group by
  sentence similarity, so wording that shares no words with an example still matches.
- Without it, words are matched with rare words counting more than common ones
  ("screenshot" says far more than "take").
- A message with several parts ("open chrome and look up F1 news") is scored part by part.

When the best groups are too close to call, the selection says it isn't confident and
the interpreter lets the language model pick from the menu instead.
"""
import math
import re

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

CONVERSATION = "(conversation)"
_EXAMPLES_SHOWN = 8
_PER_GROUP = 2
_MAX_GROUPS = 4
_OPERATION = re.compile(r'"operation": "([a-z_]+)"')
_PARTS = re.compile(r"[,;]|\band then\b|\bthen\b|\band\b|\balso\b", re.I)
# How sure a score must be. Meaning scores are cosine similarities; word scores are the
# share of the message's (rarity-weighted) words that a group contains.
_CONFIDENT = {"meaning": (0.30, 0.05), "words": (0.30, 0.08)}
_FUSION_K = 3


@dataclass
class Group:
    name: str
    operations: Set[str]
    description: str
    examples: List[str] = field(default_factory=list)  # full example lines, as shown to the model
    # What each example contributes to this ability's meaning: the whole request, or for a
    # multi-step one only the step that uses this ability.
    phrases: List[str] = field(default_factory=list)


@dataclass
class Selection:
    operations: Set[str]          # operations whose full instructions are shown
    examples: List[str]           # example lines shown, best first
    confident: bool
    method: str                   # "meaning", "words" or "model" (the language model picked)
    scores: List[Tuple[str, float]] = field(default_factory=list)


def example_phrase(line: str) -> str:
    """'"open calci" -> {...}' -> 'open calci' (an example's request, quotes and notes removed)."""
    head = line.split(" -> ", 1)[0]
    return " / ".join(re.findall(r'"([^"]+)"', head)) or head.strip('" ')


def _words(text: str) -> List[str]:
    out = []
    for word in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(word) <= 2:
            continue
        for suffix in ("ing", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        out.append(word)
    return out


def parse_groups(operations_text: str, example_lines: Sequence[str]) -> List[Group]:
    """One group per ability line of the menu, plus one for conversation."""
    groups: List[Group] = []
    for line in operations_text.splitlines():
        head, _, description = line.partition(":")
        names = set(re.findall(r'"([a-z_]+)"', head))
        if names:
            groups.append(Group(" ".join(sorted(names)), names, description.split(" Target:")[0].strip()))
    talk = Group(CONVERSATION, set(), "conversation, questions answered from knowledge, remembering things")
    for line in example_lines:
        steps = _OPERATION.findall(line.split(" -> ", 1)[-1])
        phrase = example_phrase(line)
        if not steps:
            talk.examples.append(line)
            talk.phrases.append(phrase)
            continue
        # A multi-step request split like messages are: each step teaches only its own ability.
        parts = [p.strip() for p in _PARTS.split(phrase) if p.strip()]
        pieces = list(zip(steps, parts)) if len(steps) > 1 and len(parts) == len(steps) else [(op, phrase) for op in steps]
        # An operation several abilities share ("open": apps, websites, files) teaches all of them.
        for group in groups:
            mine = [text for op, text in pieces if op in group.operations]
            if mine:
                group.examples.append(line)
                group.phrases.append(" ".join(dict.fromkeys(mine)))
    return groups + [talk]


class AbilitySelector:
    def __init__(self, embedder=None):
        self.embedder = embedder

    def select(self, message: str, operations_text: str, example_lines: Sequence[str],
               always: Sequence[str] = ()) -> Selection:
        groups = parse_groups(operations_text, example_lines)
        parts = [p.strip() for p in _PARTS.split(message) if len(p.strip()) > 2] or [message]
        if message not in parts:
            parts.insert(0, message)
        methods = {"words": self._word_scores(parts, groups)}
        meaning = self._meaning(parts, groups)
        if meaning is not None:
            methods["meaning"] = meaning

        # Each method ranks the abilities; the rankings are combined (reciprocal rank fusion),
        # so a blind spot of one method ("close notepad" sounds like "note") is covered by the other.
        fused: Dict[str, float] = {g.name: 0.0 for g in groups}
        winners: Dict[str, Tuple[str, float, float]] = {}
        for method, (group_scores, _, _) in methods.items():
            ranked = sorted(group_scores.items(), key=lambda item: -item[1])
            for rank, (name, _) in enumerate(ranked):
                fused[name] += 1.0 / (_FUSION_K + rank)
            second = ranked[1][1] if len(ranked) > 1 else 0.0
            winners[method] = (ranked[0][0], ranked[0][1], ranked[0][1] - second)
        ranked = sorted(fused.items(), key=lambda item: -item[1])
        chosen = [name for name, _ in ranked[:_MAX_GROUPS]]
        # Several parts may each want a different ability ("open chrome and search F1 news").
        for method, (_, _, per_part) in methods.items():
            for name in self._part_winners(parts, groups, per_part, _CONFIDENT[method][0]):
                if name not in chosen and len(chosen) < _MAX_GROUPS + 2:
                    chosen.append(name)

        # The best few are all shown, so the model chooses among them itself; it only needs help
        # when nothing fits well: no method finds a good match and it doesn't read as conversation.
        best = methods.get("meaning") or methods["words"]
        tools_best = max(score for name, score in best[0].items() if name != CONVERSATION)
        floor = _CONFIDENT["meaning" if "meaning" in methods else "words"][0]
        confident = tools_best >= floor or ranked[0][0] == CONVERSATION
        example_scores = (methods.get("meaning") or methods["words"])[1]
        method = "+".join(sorted(methods))
        return self._build(groups, chosen, example_scores, always, confident, method,
                           [(name, round(score, 4)) for name, score in ranked])

    def with_operations(self, operations: Set[str], message: str, operations_text: str,
                        example_lines: Sequence[str], always: Sequence[str] = ()) -> Selection:
        """The selection for abilities the language model picked itself."""
        groups = parse_groups(operations_text, example_lines)
        chosen = [g.name for g in groups if g.operations & operations] or [CONVERSATION]
        scored = self._meaning([message], groups) or self._word_scores([message], groups)
        return self._build(groups, chosen, scored[1], always, True, "model", [])

    # ------------------------------------------------------------- scoring
    # Each returns (score per group, score per example line, score per group per message part).

    def _meaning(self, parts: List[str], groups: List[Group]):
        if self.embedder is None:
            return None
        texts = list(dict.fromkeys([g.description for g in groups] + [p for g in groups for p in g.phrases]))
        vectors = self.embedder.embed(parts + texts)
        if vectors is None:
            return None
        similarity = vectors[: len(parts)] @ vectors[len(parts):].T  # parts x texts
        index = {text: i for i, text in enumerate(texts)}
        group_scores: Dict[str, float] = {}
        example_scores: Dict[str, float] = {}
        per_part: Dict[str, Dict[str, float]] = {}
        for g in groups:
            # The description says less than a real example request, so it counts a little less.
            scores = similarity[:, index[g.description]] * 0.9
            if g.phrases:
                scores = np.maximum(scores, similarity[:, [index[p] for p in g.phrases]].max(axis=1))
            group_scores[g.name] = float(scores.max())
            per_part[g.name] = {parts[i]: float(scores[i]) for i in range(len(parts))}
            for line, phrase in zip(g.examples, g.phrases):
                example_scores[line] = float(similarity[:, index[phrase]].max())
        return group_scores, example_scores, per_part

    def _word_scores(self, parts: List[str], groups: List[Group]):
        documents = [set(_words(g.description + " " + " ".join(g.phrases))) for g in groups]
        documents += [set(_words(p)) for g in groups for p in g.phrases]
        frequency: Dict[str, int] = {}
        for doc in documents:
            for word in doc:
                frequency[word] = frequency.get(word, 0) + 1
        total = len(documents)

        def weight(word: str) -> float:
            return math.log((total + 1) / (frequency.get(word, 0) + 1)) + 1.0

        def score(text_words: Set[str], doc: Set[str]) -> float:
            mass = sum(weight(w) for w in text_words)
            return sum(weight(w) for w in text_words & doc) / mass if mass else 0.0

        group_scores: Dict[str, float] = {}
        example_scores: Dict[str, float] = {}
        per_part: Dict[str, Dict[str, float]] = {}
        for g in groups:
            doc = set(_words(g.description + " " + " ".join(g.phrases)))
            per_part[g.name] = {p: score(set(_words(p)), doc) for p in parts}
            group_scores[g.name] = max(per_part[g.name].values())
            for line, phrase in zip(g.examples, g.phrases):
                example_scores[line] = max(score(set(_words(p)), set(_words(phrase))) for p in parts)
        return group_scores, example_scores, per_part

    @staticmethod
    def _part_winners(parts, groups, per_part, floor) -> List[str]:
        if len(parts) <= 2:  # the whole message plus at most one part: nothing extra to find
            return []
        # Every part's best ability first, then each part's runner-up: an example teaching several
        # abilities ("open chrome, look up F1 news") can lift a neighbour above the real one.
        ranked_parts = [sorted(groups, key=lambda g: -per_part[g.name][part])[:2] for part in parts[1:]]
        winners = []
        for place in range(2):
            for part, ranked in zip(parts[1:], ranked_parts):
                if place < len(ranked):
                    best = ranked[place]
                    if per_part[best.name][part] >= floor and best.name != CONVERSATION and best.name not in winners:
                        winners.append(best.name)
        return winners

    # ------------------------------------------------------------- the result

    @staticmethod
    def _build(groups, chosen, example_scores, always, confident, method, ranked) -> Selection:
        by_name = {g.name: g for g in groups}
        shown: List[str] = []
        for name in chosen:
            best = sorted(by_name[name].examples, key=lambda line: -example_scores.get(line, 0.0))
            shown += [line for line in best[:_PER_GROUP] if line not in shown]
        for line in sorted(example_scores, key=lambda line: -example_scores[line]):
            if len(shown) >= _EXAMPLES_SHOWN:
                break
            if line not in shown:
                shown.append(line)
        shown += [line for group in groups for line in group.examples
                  if line.startswith(tuple(always)) and line not in shown]
        operations = set().union(*(by_name[name].operations for name in chosen))
        return Selection(operations, shown, confident, method, [(n, round(s, 3)) for n, s in ranked[:4]])
