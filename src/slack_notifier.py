"""Slack Incoming Webhook으로 보도자료 알림 전송.

Block Kit을 사용해 보기 좋게 포맷팅한다.
- 헤더: 기관 이모지 + 제목
- 본문: 요약 텍스트 (PDF 추출본 또는 description)
- 컨텍스트: 발행 시각
- 첨부파일 링크 (PDF/HWP 등)
- 원문 보기 버튼
"""
from __future__ import annotations
from typing import Any, Dict, List

import requests

from .models import PressItem


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def build_blocks(item: PressItem) -> List[Dict[str, Any]]:
    """하나의 PressItem을 Slack Block Kit 블록 리스트로 변환."""
    title_line = f"{item.source_emoji} *{item.source_name}* 보도자료"
    # 본문 요약: body_text가 있으면 우선, 없으면 summary
    body = (item.body_text or item.summary or "").strip()
    body = _truncate(body, 1800)  # Slack section text 한도 3000자지만 여유있게
    if not body:
        body = "_본문 자동추출 실패. 원문에서 직접 확인해주세요._"

    blocks: List[Dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{title_line}\n*<{item.link}|{_truncate(item.title, 140)}>*",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
        },
    ]

    # 첨부 파일
    if item.attachments:
        lines = []
        for a in item.attachments[:6]:
            label = _truncate(a.filename, 60)
            lines.append(f"• <{a.url}|📎 {label}> `.{a.ext}`")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*첨부파일*\n" + "\n".join(lines)},
        })

    # 컨텍스트 (발행 시각)
    if item.published_at:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🕒 {item.published_at.strftime('%Y-%m-%d %H:%M')}"
                            f"  |  원문: <{item.link}|보기>",
                }
            ],
        })
    else:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"원문: <{item.link}|보기>"},
            ],
        })

    blocks.append({"type": "divider"})
    return blocks


def send_items(items: List[PressItem], webhook_url: str) -> List[PressItem]:
    """여러 PressItem을 Slack에 순차 전송. 성공한 item 리스트 반환."""
    if not items:
        return []

    sent: List[PressItem] = []
    for item in items:
        blocks = build_blocks(item)
        payload = {
            "text": f"{item.source_name} 보도자료: {item.title}",  # fallback
            "blocks": blocks,
        }
        try:
            r = requests.post(webhook_url, json=payload, timeout=15)
            r.raise_for_status()
            sent.append(item)
        except requests.RequestException as e:
            print(f"[slack] 전송 실패 {item.uid}: {e}")
    return sent
