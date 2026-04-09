"""기관별 HTML 목록 페이지 파서 모음.

fetcher.fetch_html() 에서 `parse_<parser_name>(source, cfg)` 를 동적으로 찾아 호출한다.
각 함수는 `List[PressItem]` 을 반환해야 한다.

새 파서 추가 방법:
1. 이 파일에 `parse_XXX_html(source, cfg)` 함수를 구현
2. sources.yaml 에 `parser: XXX_html` 로 지정
"""
from __future__ import annotations
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from ..models import PressItem
from ..fetcher import _http_session, _make_uid  # noqa: WPS450


# ----------------------------------------------------------------------
# 공정거래위원회 보도자료 (예시: korea.kr 통합 RSS가 실패할 때 대체용)
# ----------------------------------------------------------------------

def parse_ftc_html(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    """공정위 보도자료 리스트 페이지를 파싱.

    TODO: 실제 셀렉터는 사이트 개편에 따라 수정 필요.
    """
    session = _http_session(cfg)
    try:
        r = session.get(source["list_url"], timeout=cfg["http"]["timeout_sec"])
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[parse_ftc_html] {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items: List[PressItem] = []
    # 예시 셀렉터 - 실제 구조 확인 후 조정해야 함
    for row in soup.select("table.board_list tbody tr"):
        a = row.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a["href"]
        from urllib.parse import urljoin
        link = urljoin(source["list_url"], href)
        items.append(PressItem(
            source_id=source["id"],
            source_name=source["name"],
            source_emoji=source.get("emoji", "📢"),
            uid=_make_uid(source["id"], link),
            title=title,
            link=link,
        ))
    return items


# ----------------------------------------------------------------------
# 아래는 플레이스홀더 - 필요 시 실제 셀렉터 채워 넣기
# ----------------------------------------------------------------------

def parse_fsc_html(source, cfg):
    return []

def parse_fss_html(source, cfg):
    return []

def parse_bok_html(source, cfg):
    return []

def parse_kca_html(source, cfg):
    return []
