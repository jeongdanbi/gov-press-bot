"""데이터 모델 정의. 간단한 dataclass로 유지."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


@dataclass
class Attachment:
    """보도자료 첨부파일 정보."""
    filename: str
    url: str
    ext: str                         # 예: "pdf", "hwp", "hwpx"
    size_bytes: Optional[int] = None
    extracted_text: Optional[str] = None  # PDF 등에서 텍스트 추출 시만 채워짐

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PressItem:
    """기관별 보도자료 1건."""
    source_id: str                   # sources.yaml의 id
    source_name: str                 # 표시 이름
    source_emoji: str
    uid: str                         # 중복 체크용 고유 키 (source_id + newsId/URL hash)
    title: str
    link: str                        # 원문 URL
    published_at: Optional[datetime] = None
    summary: str = ""                # RSS description 또는 HTML 본문 앞부분
    body_text: str = ""              # PDF/HTML에서 추출한 본문 전체(최대 글자수 이내)
    attachments: List[Attachment] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d
