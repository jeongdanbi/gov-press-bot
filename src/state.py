"""seen.json - 이미 알림 전송한 항목 저장.

GitHub Actions에서 돌릴 때는 state/seen.json을 레포에 커밋해서 영속화한다.
구조: {"source_id": ["uid1", "uid2", ...]} 형태의 dict. 한 source당 최대 500건만 유지.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Set

from .config import STATE_DIR, STATE_FILE


MAX_PER_SOURCE = 500


class SeenStore:
    def __init__(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, list] = {}
        self._load()

    def _load(self) -> None:
        if STATE_FILE.exists():
            try:
                self._data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}
        else:
            self._data = {}

    def is_seen(self, source_id: str, uid: str) -> bool:
        return uid in self._data.get(source_id, [])

    def mark(self, source_id: str, uid: str) -> None:
        lst = self._data.setdefault(source_id, [])
        if uid not in lst:
            lst.append(uid)
        # 최신 N개만 유지
        if len(lst) > MAX_PER_SOURCE:
            self._data[source_id] = lst[-MAX_PER_SOURCE:]

    def save(self) -> None:
        STATE_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def source_ids(self) -> Set[str]:
        return set(self._data.keys())
