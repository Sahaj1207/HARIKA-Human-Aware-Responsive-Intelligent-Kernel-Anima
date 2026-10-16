"""The most recent list HARIKA showed the user (web results or files).

"Open the second one" refers to whatever was listed last, so search tools
record their results here and the result-opening capability reads them.
"""
from typing import Dict, List, Optional

_last: List[Dict[str, str]] = []
_source: Optional[str] = None


def remember(source: str, items: List[Dict[str, str]]) -> None:
    global _last, _source
    _last, _source = list(items), source


def get(position: int) -> Optional[Dict[str, str]]:
    return _last[position] if 0 <= position < len(_last) else None


def count() -> int:
    return len(_last)


def source() -> Optional[str]:
    return _source
