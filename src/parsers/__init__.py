"""기관별 HTML 목록 페이지 파서 모음.

fetcher.fetch_html() 에서 `parse_<parser_name>(source, cfg)` 를 동적으로 찾아 호출한다.
각 함수는 `List[PressItem]` 을 반환해야 한다.

새 파서 추가 방법:
1. 이 파일에 `parse_XXX_html(source, cfg)` 함수를 구현
2. sources.yaml 에 `parser: XXX_html` 로 지정
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urljoin

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
# 금융감독원 보도자료 (서버 렌더 HTML 표, RSS 없음)
# ----------------------------------------------------------------------

def _get_html(source_id: str, url: str, cfg: Dict[str, Any]):
    import time as _time
    session = _http_session(cfg)
    max_retries = cfg["http"].get("retry", 2)
    for attempt in range(max_retries + 1):
        try:
            r = session.get(url, timeout=cfg["http"]["timeout_sec"])
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt < max_retries:
                _time.sleep(5 * (attempt + 1))
            else:
                print(f"[{source_id}] 목록 요청 최종 실패: {e}")
    return None


def _parse_ymd(raw: str):
    m = re.search(r"(\d{4})[-.](\d{2})[-.](\d{2})", raw or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_fss_html(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    """금감원 보도자료 목록(B0000188). tbody tr > td.title > a, 날짜는 YYYY-MM-DD 셀."""
    r = _get_html(source["id"], source["list_url"], cfg)
    if r is None:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    items: List[PressItem] = []
    for row in soup.select("tbody tr"):
        a = row.select_one("td.title a[href]")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        link = urljoin(source["list_url"], a["href"].strip())
        pub = None
        for td in row.find_all("td", recursive=False):
            pub = _parse_ymd(td.get_text(strip=True))
            if pub:
                break
        if not title:
            continue
        items.append(PressItem(
            source_id=source["id"],
            source_name=source["name"],
            source_emoji=source.get("emoji", "📢"),
            uid=_make_uid(source["id"], link),
            title=title,
            link=link,
            published_at=pub,
        ))
    return items


# ----------------------------------------------------------------------
# 서울특별시 보도자료 (목록 링크가 javascript:fnTbbsView('번호') -> ?bbsNo=158&nttNo=번호)
# ----------------------------------------------------------------------

def parse_seoul_html(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    r = _get_html(source["id"], source["list_url"], cfg)
    if r is None:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    bbs_no = source.get("bbs_no", "158")
    items: List[PressItem] = []
    for row in soup.select("tbody tr"):
        a = row.select_one("td.sib-lst-type-basic-subject a[href]")
        if not a:
            continue
        m = re.search(r"fnTbbsView\('(\d+)'\)", a["href"])
        if not m:
            continue
        title = a.get_text(" ", strip=True)
        link = f"{source['list_url'].split('?')[0]}?bbsNo={bbs_no}&nttNo={m.group(1)}"
        pub = None
        for td in row.find_all("td", recursive=False):
            pub = _parse_ymd(td.get_text(strip=True))
            if pub:
                break
        if not title:
            continue
        items.append(PressItem(
            source_id=source["id"],
            source_name=source["name"],
            source_emoji=source.get("emoji", "📢"),
            uid=_make_uid(source["id"], link),
            title=title,
            link=link,
            published_at=pub,
        ))
    return items


# ----------------------------------------------------------------------
# 아래는 플레이스홀더 - 필요 시 실제 셀렉터 채워 넣기
# ----------------------------------------------------------------------

def parse_fsc_html(source, cfg):
    return []

def parse_bok_html(source, cfg):
    return []

def parse_kca_html(source, cfg):
    return []
