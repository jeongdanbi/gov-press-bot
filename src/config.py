"""sources.yaml 로더와 런타임 설정."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
STATE_DIR = ROOT / "state"
STATE_FILE = STATE_DIR / "seen.json"


def load_sources() -> Dict[str, Any]:
    """sources.yaml 로드."""
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_slack_webhook() -> str:
    """Slack 웹훅 URL 조회. 환경변수에서만 읽는다."""
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        raise RuntimeError(
            "SLACK_WEBHOOK_URL 환경변수가 비어있습니다. "
            "로컬 테스트 시 .env 또는 GitHub Actions secrets 설정 필요."
        )
    return url


def get_enabled_sources(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [s for s in cfg.get("sources", []) if s.get("enabled")]
