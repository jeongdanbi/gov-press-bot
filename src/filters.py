"""키워드 필터. sources.yaml 의 keywords_include/exclude 기반."""
from __future__ import annotations
from typing import Dict, Any

from .models import PressItem


def passes_filter(item: PressItem, source: Dict[str, Any]) -> bool:
    """include가 비어있지 않으면 하나라도 매칭되어야 통과.
    exclude가 매칭되면 제외."""
    text = f"{item.title} {item.summary}".lower()

    includes = [k.lower() for k in source.get("keywords_include", []) if k]
    excludes = [k.lower() for k in source.get("keywords_exclude", []) if k]

    if excludes and any(kw in text for kw in excludes):
        return False
    if includes and not any(kw in text for kw in includes):
        return False
    return True
