# gov-press-bot

정부기관 보도자료를 실시간으로 수집해 Slack으로 알림을 보내주는 봇.
GitHub Actions 크론으로 15분마다 실행. PDF 첨부파일은 본문을 추출해 요약까지 함께 전송.

## 기본 수집 대상 (6개)

| 기관 | 이모지 | 방식 |
|---|---|---|
| 금융위원회 | 🏦 | korea.kr RSS |
| 금융감독원 | 🛡️ | korea.kr RSS |
| 한국은행 | 💴 | korea.kr RSS |
| 공정거래위원회 | ⚖️ | korea.kr RSS |
| 기획재정부 | 🏛️ | korea.kr RSS |
| 국세청 | 📊 | korea.kr RSS |

추가 기관은 `config/sources.yaml` 에서 얼마든지 추가 가능.

## 아키텍처

```
GitHub Actions (cron */15)
   │
   ▼
src/main.py
   ├─ fetcher.fetch_source()       ← RSS/HTML 수집
   ├─ filters.passes_filter()      ← 키워드 필터
   ├─ fetcher.enrich_item()        ← 원문/PDF 본문 추출
   ├─ state.SeenStore              ← 중복 방지
   └─ slack_notifier.send_items()  ← Slack 전송
        │
        ▼
   Slack 채널
```

## 폴더 구조

```
gov-press-bot/
├── config/
│   └── sources.yaml        # 수집 대상 정의 (여기만 수정하면 OK)
├── src/
│   ├── main.py             # 진입점
│   ├── config.py           # 설정 로더
│   ├── models.py           # PressItem, Attachment
│   ├── fetcher.py          # RSS/HTML 수집
│   ├── extractor.py        # 본문/첨부 추출, PDF 파싱
│   ├── filters.py          # 키워드 필터
│   ├── slack_notifier.py   # Slack Block Kit 포맷팅
│   ├── state.py            # seen.json 관리
│   └── parsers/
│       └── __init__.py     # 기관별 커스텀 HTML 파서 (필요 시)
├── state/
│   └── seen.json           # 이미 알림 보낸 항목 기록 (자동 생성/커밋)
├── .github/workflows/
│   └── press-bot.yml       # GitHub Actions
├── requirements.txt
└── .env.example
```

## 로컬 테스트

### 1. Python 3.12 + 가상환경

```powershell
cd D:\클로드\gov-press-bot
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Slack Webhook URL 설정

```powershell
# PowerShell
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

Slack Webhook 만드는 법:
1. https://api.slack.com/apps → Create New App → From scratch
2. Incoming Webhooks 활성화 → Add New Webhook to Workspace
3. 알림 받을 채널 선택 → 생성된 URL 복사

### 3. 실행

```powershell
# Slack 전송 없이 콘솔만
python -m src.main --dry-run

# 특정 기관만
python -m src.main --dry-run --source fsc

# 실제 전송
python -m src.main
```

**첫 실행 시 주의**: 기존 보도자료가 한꺼번에 쏟아지지 않도록, 첫 실행에서는
각 기관의 현재 목록을 모두 "seen" 처리하고 알림은 보내지 않습니다.
다음 실행부터 새로 올라온 것만 알림이 옵니다.

## GitHub 배포

### 1. 새 레포 만들기

```powershell
cd D:\클로드\gov-press-bot
git init
git add .
git commit -m "initial: gov-press-bot"
git branch -M main
git remote add origin https://github.com/YOURNAME/gov-press-bot.git
git push -u origin main
```

### 2. GitHub Secrets 등록

레포 → Settings → Secrets and variables → Actions → New repository secret
- Name: `SLACK_WEBHOOK_URL`
- Value: 위에서 만든 Slack Webhook URL

### 3. Actions 활성화

- 레포 → Actions 탭 → "I understand..." 클릭
- `gov-press-bot` 워크플로우가 보임 → Enable
- 수동 실행: "Run workflow" 버튼
- 이후로는 15분마다 자동 실행

## 기관 추가하기

### 방법 A: korea.kr에 있는 부처 추가

```yaml
# config/sources.yaml
sources:
  - id: msit
    name: 과학기술정보통신부
    emoji: "📡"
    type: korea_kr_dept
    dept_code: msit        # korea.kr/rss/dept_msit.xml
    enabled: true
```

korea.kr 부처 코드 참고: https://www.korea.kr/etc/rss.do

### 방법 B: 직접 RSS URL 지정

```yaml
  - id: moef_direct
    name: 기획재정부 (자체 RSS)
    emoji: "🏛️"
    type: rss
    feed_url: "https://www.moef.go.kr/mn/rss/rssService.do?type=press"
    enabled: true
```

### 방법 C: HTML 페이지 (RSS 없는 사이트)

1. `src/parsers/__init__.py` 에 `parse_XXX_html(source, cfg)` 함수 추가
2. `sources.yaml` 에 등록:

```yaml
  - id: kca
    name: 한국소비자원
    emoji: "🛒"
    type: html
    list_url: "https://www.kca.go.kr/home/sub.do?menukey=4002"
    parser: kca_html
    enabled: true
```

## 키워드 필터

특정 키워드만 받고 싶을 때:

```yaml
  - id: fsc
    name: 금융위원회
    type: korea_kr_dept
    dept_code: fsc
    enabled: true
    keywords_include: ["가상자산", "AI", "핀테크"]    # 하나라도 매칭되면 통과
    keywords_exclude: ["인사", "채용공고"]              # 매칭되면 제외
```

## Slack 알림에서 기사 쓰기 워크플로

1. Slack에 보도자료 알림이 옴
2. 관심 있는 건 → 메시지의 *원문 링크* 복사
3. Claude Code 대화창에 붙여넣기 → "이 보도자료로 기사 써줘"
4. 완성된 기사를 기존 CMS 업로더(`D:\클로드\cms-uploader`)로 전송

## 트러블슈팅

- **RSS가 비어있음**: `python -m src.main --dry-run --source fsc` 로 확인.
  RSS가 변경됐을 수 있음 → `fetcher.py`의 `KOREA_KR_RSS_FMT` 확인.
- **본문이 안 뽑힘**: `extractor.py`의 `BODY_SELECTORS` 에 해당 사이트 셀렉터 추가.
- **PDF 텍스트 빈값**: 스캔 이미지형 PDF는 OCR 필요. 현재 미지원.
- **Slack 알림 안 옴**: `SLACK_WEBHOOK_URL` 오타 또는 채널 삭제 확인.
- **중복 알림**: `state/seen.json` 이 커밋되지 않으면 매 실행마다 새 건으로 인식됨.
  GitHub Actions의 `Commit seen.json` 단계가 성공하는지 확인.

## 라이선스

개인 사용 목적. 자유롭게 수정.
