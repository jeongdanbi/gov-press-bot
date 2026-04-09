"""원문 페이지에서 본문 텍스트와 첨부파일 URL을 추출하고,
PDF 첨부는 다운받아서 텍스트까지 뽑아낸다.
"""
from __future__ import annotations
import io
import os
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import Attachment


ATTACH_EXT_PATTERN = re.compile(r"\.(pdf|hwp|hwpx|docx|doc)(\?|$)", re.IGNORECASE)


def _guess_ext(url: str, filename: str = "") -> str:
    m = ATTACH_EXT_PATTERN.search(filename or url)
    if m:
        return m.group(1).lower()
    return ""


def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


# ----------------------------------------------------------------------
# 본문 + 첨부파일 추출
# ----------------------------------------------------------------------

BODY_SELECTORS = [
    # korea.kr 정책브리핑 보도자료 상세
    "div.article_body",
    "div#article_body",
    "div.view_con",
    "div.article_cont",
    "div.news_con",
    # 일반 기관 사이트 흔한 패턴
    "div.view-content",
    "div.board_view",
    "div.bbs_view",
    "div.content",
    "article",
]


def _extract_body(soup: BeautifulSoup) -> str:
    for sel in BODY_SELECTORS:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 100:
            return _clean_text(node.get_text(" ", strip=True))
    # 전부 실패 시, <p> 태그를 모두 긁는다
    ps = soup.find_all("p")
    text = " ".join(p.get_text(" ", strip=True) for p in ps)
    return _clean_text(text)


def _extract_attachments(soup: BeautifulSoup, base_url: str) -> List[Attachment]:
    seen = set()
    out: List[Attachment] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        fname_guess = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
        ext = _guess_ext(href, fname_guess)
        if not ext:
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        seen.add(full)
        # 파일명 유추
        if not fname_guess or len(fname_guess) > 120:
            fname_guess = os.path.basename(urlparse(full).path) or f"file.{ext}"
        out.append(Attachment(
            filename=fname_guess,
            url=full,
            ext=ext,
        ))
    return out


def extract_body_and_attachments(
    html: str,
    base_url: str,
    cfg: Dict[str, Any],
) -> Tuple[str, List[Attachment]]:
    soup = BeautifulSoup(html, "html.parser")
    body = _extract_body(soup)
    attachments = _extract_attachments(soup, base_url)

    # 옵션에 따라 PDF 다운로드 및 텍스트 추출
    if cfg["extract"].get("download_pdf", False):
        for att in attachments:
            if att.ext == "pdf":
                txt = _download_and_extract_pdf(
                    att.url,
                    max_mb=cfg["extract"].get("max_file_size_mb", 30),
                    user_agent=cfg["http"]["user_agent"],
                    timeout=cfg["http"]["timeout_sec"],
                )
                if txt:
                    att.extracted_text = txt
                    # 본문이 너무 짧으면 PDF 본문으로 보강
                    if len(body) < 200 and len(txt) > 200:
                        body = txt
    return body, attachments


# ----------------------------------------------------------------------
# PDF 다운로드 + 텍스트 추출
# ----------------------------------------------------------------------

def _download_and_extract_pdf(
    url: str,
    max_mb: int,
    user_agent: str,
    timeout: int,
) -> str:
    """PDF 바이트를 받아 pdfplumber로 텍스트 추출. 실패 시 빈 문자열."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
            stream=True,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[pdf] 다운로드 실패 {url}: {e}")
        return ""

    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > max_mb * 1024 * 1024:
        print(f"[pdf] {url} 용량 초과 ({int(content_length)/1024/1024:.1f}MB)")
        return ""

    max_bytes = max_mb * 1024 * 1024
    buf = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=65536):
        buf.write(chunk)
        if buf.tell() > max_bytes:
            print(f"[pdf] {url} 스트림 중 용량 초과")
            return ""
    buf.seek(0)

    # pdfplumber 우선, 실패 시 pypdf 시도
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(buf) as pdf:
            pages = []
            for page in pdf.pages[:30]:  # 최대 30 페이지만
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
    except Exception as e:
        print(f"[pdf] pdfplumber 실패, pypdf 시도: {e}")
        try:
            buf.seek(0)
            from pypdf import PdfReader
            reader = PdfReader(buf)
            text = "\n".join(p.extract_text() or "" for p in reader.pages[:30])
        except Exception as e2:
            print(f"[pdf] pypdf도 실패: {e2}")
            return ""

    return _clean_text(text)
