"""보도자료 수집 모듈.

- korea_kr_dept: korea.kr 부처 RSS 피드 파싱
- rss: 일반 RSS/Atom 피드 파싱
- html: 기관 자체 홈페이지 HTML 스크래핑 (parsers/ 모듈에 위임)
"""
from __future__ import annotations
import hashlib
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs

import feedparser
import requests
from bs4 import BeautifulSoup

from .models import PressItem


def _http_session(cfg: Dict[str, Any]) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": cfg["http"]["user_agent"],
        "Accept-Language": "ko,en;q=0.9",
    })
    return s


def _make_uid(source_id: str, link: str) -> str:
    """링크 안 newsId 파라미터가 있으면 그걸 쓰고, 없으면 URL 해시."""
    qs = parse_qs(urlparse(link).query)
    if "newsId" in qs:
        return f"{source_id}:{qs['newsId'][0]}"
    h = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
    return f"{source_id}:{h}"


def _strip_html(html: str, max_len: int = 400) -> str:
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:max_len]


def _parse_pubdate(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------
# RSS 공통 파서
# ----------------------------------------------------------------------

def fetch_rss(source: Dict[str, Any], feed_url: str, cfg: Dict[str, Any]) -> List[PressItem]:
    """RSS feed_url을 받아 PressItem 리스트 반환."""
    session = _http_session(cfg)
    try:
        resp = session.get(feed_url, timeout=cfg["http"]["timeout_sec"])
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[fetch_rss] {source['id']} 실패: {e}")
        return []

    parsed = feedparser.parse(resp.content)
    items: List[PressItem] = []
    for entry in parsed.entries:
        link = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        if not link or not title:
            continue

        pub = _parse_pubdate(entry.get("published", ""))
        summary = _strip_html(entry.get("summary", ""), max_len=500)

        items.append(PressItem(
            source_id=source["id"],
            source_name=source["name"],
            source_emoji=source.get("emoji", "📢"),
            uid=_make_uid(source["id"], link),
            title=title,
            link=link,
            published_at=pub,
            summary=summary,
        ))
    return items


# ----------------------------------------------------------------------
# korea.kr 부처 RSS
# ----------------------------------------------------------------------

KOREA_KR_RSS_FMT = "https://www.korea.kr/rss/dept_{code}.xml"
KOREA_KR_ALL_RSS = "https://www.korea.kr/rss/pressrelease.xml"


def fetch_korea_kr_dept(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    code = source.get("dept_code", "").lower()
    if not code:
        print(f"[korea_kr_dept] {source['id']}: dept_code 누락")
        return []
    feed_url = KOREA_KR_RSS_FMT.format(code=code)
    return fetch_rss(source, feed_url, cfg)


def fetch_korea_kr_all(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    """korea.kr 통합 보도자료 RSS에서 제목 접두사 [기관명] 매칭으로 필터링.

    source['title_prefix_match'] 의 문자열 중 하나라도 제목 대괄호 안에 있으면 매칭.
    예: title_prefix_match: ["금감원", "금융감독원"]
       제목 "[금감원]주가조작 적발..." → 매칭
    """
    prefixes = source.get("title_prefix_match", [])
    if not prefixes:
        print(f"[korea_kr_all] {source['id']}: title_prefix_match 누락")
        return []

    all_items = fetch_rss(source, KOREA_KR_ALL_RSS, cfg)
    filtered: List[PressItem] = []
    for it in all_items:
        # 제목 접두사 [기관명] 추출
        m = re.match(r"^\[([^\]]+)\]", it.title)
        if not m:
            continue
        bracket = m.group(1).strip()
        if any(p in bracket for p in prefixes):
            # 제목에서 대괄호 제거 (더 깔끔한 표시)
            it.title = it.title[m.end():].strip()
            filtered.append(it)
    return filtered


# ----------------------------------------------------------------------
# HTML 스크래핑 (parsers/ 모듈에 위임)
# ----------------------------------------------------------------------

def fetch_html(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    parser_name = source.get("parser", "")
    try:
        from . import parsers  # noqa: WPS433
        fn = getattr(parsers, f"parse_{parser_name}", None)
    except ImportError:
        fn = None
    if fn is None:
        print(f"[fetch_html] {source['id']}: parser '{parser_name}' 없음")
        return []
    return fn(source, cfg)


# ----------------------------------------------------------------------
# 디스패처
# ----------------------------------------------------------------------

def fetch_source(source: Dict[str, Any], cfg: Dict[str, Any]) -> List[PressItem]:
    t = source.get("type")
    if t == "korea_kr_dept":
        return fetch_korea_kr_dept(source, cfg)
    if t == "korea_kr_all":
        return fetch_korea_kr_all(source, cfg)
    if t == "rss":
        return fetch_rss(source, source["feed_url"], cfg)
    if t == "html":
        return fetch_html(source, cfg)
    print(f"[fetch_source] 알 수 없는 type: {t} ({source.get('id')})")
    return []


# ----------------------------------------------------------------------
# 본문/첨부 채움 (원문 페이지 방문)
# ----------------------------------------------------------------------

def enrich_item(item: PressItem, cfg: Dict[str, Any]) -> PressItem:
    """원문 페이지에 접근해서 본문 텍스트와 첨부파일 링크 수집.

    - korea.kr pressReleaseView.do: 본문 class 여러 패턴 시도
    - 그 외: 일반 HTML 긁어서 본문 추측
    - 첨부파일: a[href$='.pdf' | '.hwp' | '.hwpx'] 추출
    """
    from .extractor import extract_body_and_attachments

    session = _http_session(cfg)
    try:
        resp = session.get(item.link, timeout=cfg["http"]["timeout_sec"])
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[enrich] {item.uid} 원문 요청 실패: {e}")
        return item

    body_text, attachments = extract_body_and_attachments(
        resp.text, base_url=item.link, cfg=cfg
    )
    max_chars = cfg["extract"]["max_body_chars"]
    item.body_text = (body_text or "")[:max_chars]
    item.attachments = attachments
    return item
