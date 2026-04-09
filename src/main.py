"""gov-press-bot 진입점.

파이프라인:
1) sources.yaml 로드
2) 각 source에 대해 RSS/HTML 수집
3) seen.json으로 중복 제거
4) 키워드 필터링
5) 원문 페이지에서 본문+첨부파일 enrich
6) Slack으로 전송
7) seen.json 갱신하여 저장

실행:
    python -m src.main
    python -m src.main --dry-run          # Slack 전송 안 함, 콘솔만
    python -m src.main --source fsc       # 특정 source만
"""
from __future__ import annotations
import argparse
import os
import sys
import time
import traceback
from typing import List

from .config import load_sources, get_slack_webhook, get_enabled_sources
from .fetcher import fetch_source, enrich_item
from .filters import passes_filter
from .models import PressItem
from .slack_notifier import send_items
from .state import SeenStore


MAX_ITEMS_PER_SOURCE = 10   # 한 번 실행에 source당 최대 N건까지만 (첫 실행 시 스팸 방지)


def run(dry_run: bool = False, only_source: str | None = None) -> int:
    cfg = load_sources()
    sources = get_enabled_sources(cfg)
    if only_source:
        sources = [s for s in sources if s["id"] == only_source]
        if not sources:
            print(f"[main] source id '{only_source}' 를 찾을 수 없음")
            return 1

    store = SeenStore()
    webhook = None
    if not dry_run:
        webhook = get_slack_webhook()

    total_new = 0
    for source in sources:
        sid = source["id"]
        print(f"\n[{sid}] {source['name']} 수집 시작 ({source['type']})")
        try:
            items = fetch_source(source, cfg)
        except Exception as e:
            print(f"[{sid}] 수집 실패: {e}")
            traceback.print_exc()
            continue

        print(f"[{sid}] 수집: {len(items)} 건")

        # 첫 실행 여부 판정: 이 source를 한 번도 본 적 없으면
        # 스팸 방지를 위해 지금 시점 이후에 올라오는 것만 알림으로 보내고,
        # 기존 건은 모두 seen으로 마킹.
        first_run = sid not in store.source_ids
        if first_run:
            print(f"[{sid}] 첫 실행 감지 → 기존 {len(items)}건 모두 seen 처리 (알림 X)")
            for it in items:
                store.mark(sid, it.uid)
            continue

        # 새 항목 추림
        new_items: List[PressItem] = []
        for it in items:
            if store.is_seen(sid, it.uid):
                continue
            if not passes_filter(it, source):
                store.mark(sid, it.uid)  # 필터 탈락해도 다음에 또 보지 않도록 기록
                continue
            new_items.append(it)

        # 최신순 정렬 (published_at desc). None은 맨 뒤로.
        new_items.sort(key=lambda x: x.published_at or 0, reverse=True)
        new_items = new_items[:MAX_ITEMS_PER_SOURCE]

        print(f"[{sid}] 새 항목: {len(new_items)} 건")

        # enrich (본문, 첨부파일)
        enriched: List[PressItem] = []
        for it in new_items:
            try:
                enriched.append(enrich_item(it, cfg))
            except Exception as e:
                print(f"[{sid}] enrich 실패 {it.uid}: {e}")
                enriched.append(it)  # 원본이라도 보냄
            time.sleep(0.5)  # rate limit

        # Slack 전송
        if dry_run:
            for it in enriched:
                print(f"  [DRY] {it.title} ({len(it.body_text)}자 본문, 첨부 {len(it.attachments)})")
                store.mark(sid, it.uid)
        else:
            sent = send_items(enriched, webhook)
            print(f"[{sid}] Slack 전송: {sent}/{len(enriched)}")
            for it in enriched:
                store.mark(sid, it.uid)

        total_new += len(enriched)

    store.save()
    print(f"\n=== 완료: 총 {total_new} 건 처리 ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="gov-press-bot")
    parser.add_argument("--dry-run", action="store_true", help="Slack 전송 없이 콘솔만 출력")
    parser.add_argument("--source", help="특정 source id만 실행 (예: fsc)")
    args = parser.parse_args()
    return run(dry_run=args.dry_run, only_source=args.source)


if __name__ == "__main__":
    sys.exit(main())
