# 비교과 프로그램 도우미

한성대학교 HS Portal의 비교과 프로그램 정보를 수집하고, 학생의 수업 시간표와 비교해 참여 가능성이 높은 프로그램을 추천하는 FastAPI 기반 웹 서비스입니다. 사용자는 시간표 이미지를 업로드하고, 서비스는 VLM으로 수업 정보를 JSON으로 추출한 뒤 편집 가능한 시간표 화면과 추천 결과 화면을 제공합니다.

## 핵심 목적

- 시간표 이미지에서 수업명, 요일, 시작/종료 시간을 구조화합니다.
- HS Portal 비교과 프로그램 목록과 상세 정보를 로컬 JSON으로 준비합니다.
- 수업 시간과 비교과 프로그램 운영 일정을 비교해 참여 가능 여부를 분류합니다.
- 학생이 확인해야 할 프로그램을 `참여 가능`, `확인 필요`, `참여 불가`로 나눠 보여줍니다.

## 현재 기능

- FastAPI 단일 서버에서 API와 정적 프론트엔드를 함께 제공
- 서버 시작 직후와 설정된 주기마다 HS Portal 비교과 데이터 백그라운드 수집/갱신
- 시간표 이미지 업로드, 미리보기, 영역 크롭, VLM 분석
- 추출된 시간표를 드래그 앤 드롭으로 수정하는 편집 화면
- 추천 API 호출 후 프로그램 목록, 검색, 필터, 상세 모달 제공
- 개발 환경 전용 JSON 직접 입력 및 `/test/` API 확인 화면
- Qwen OpenAI-compatible Vision API 연동
- pytest 기반 API, 추천 알고리즘, LLM 내부 처리 검증

## 프로젝트 구조

```text
/
├─ main.py
│  └─ FastAPI 앱 생성, 라우터 등록, 정적 프론트엔드 마운트, 크롤러 lifespan 관리
├─ backend/
│  ├─ api/
│  │  └─ heartbeat, hsportal, timetable, recommendations API 라우터
│  ├─ hsportal/
│  │  └─ HS Portal 목록/상세 크롤링, HTML 파싱, JSON 저장
│  ├─ config.py
│  └─ recommendation.py
├─ frontend/
│  └─ public/
│     └─ 메인, 시간표 편집, 추천 결과, 테스트용 정적 HTML/CSS/JS
├─ llm/
│  ├─ tasks/
│  │  └─ 시간표 추출 task 정의
│  ├─ config.py
│  ├─ media.py
│  ├─ qwen_client.py
│  ├─ schemas.py
│  └─ service.py
├─ util/
│  └─ 로깅 설정과 이미지 전처리 공통 유틸리티
├─ tests/
│  └─ API, 추천 로직, LLM 내부 처리 테스트
└─ recommendation_algorithm_explanation.html
   └─ 추천 알고리즘 설명용 정적 문서
```

## 디렉터리별 역할 분담

| 디렉터리 | 주요 책임 | 직접 연동 대상 |
| --- | --- | --- |
| `backend` | API 라우팅, 비교과 데이터 조회, 추천 계산, HS Portal 데이터 관리 | `main.py`, `llm`, `frontend` |
| `frontend` | 사용자 화면, 업로드/크롭/편집/추천 결과 UI, 브라우저 상태 저장 | `backend` API |
| `llm` | Qwen Vision API 호출, 이미지 payload 구성, JSON 응답 파싱/검증 | `backend.api.timetable`, `util` |
| `util` | 앱 전역 로깅, 이미지 포맷 검사와 WebP 정규화 | `main.py`, `llm.media` |
| `tests` | API와 내부 로직 회귀 테스트 | `backend`, `llm`, `util` |

## 실행 흐름

1. `main.py`가 FastAPI 앱을 만들고 `/api` 라우터와 `frontend/public` 정적 파일을 등록합니다.
2. 앱 lifespan 시작 시 HS Portal 크롤러 주기 실행 task가 백그라운드로 예약됩니다.
3. 저장된 `backend/hsportal/programs.json`이 없거나 수집 정책이 바뀌면 전체 수집을 수행합니다.
4. 저장 데이터가 있으면 목록 첫 페이지의 최신 프로그램 ID를 cursor와 비교해 필요한 경우에만 증분 수집합니다.
5. 수집 1회가 끝나면 `HSPORTAL_CRAWL_INTERVAL_HOURS` 값만큼 대기한 뒤 같은 갱신 작업을 반복합니다.
6. 사용자가 시간표 이미지를 업로드하면 `/api/timetable/extract`가 이미지를 검증하고 WebP로 정규화합니다.
7. `llm` 계층이 Qwen Vision API에 시간표 추출 task를 요청하고 `TimetableExtractionResult`로 검증합니다.
8. 프론트엔드는 추출된 시간표를 `sessionStorage`에 저장하고 `/timetable/` 편집 화면으로 이동합니다.
9. 편집이 끝나면 `/api/recommendations`가 수업 시간과 비교과 프로그램 일정을 비교합니다.
10. 결과는 점수순으로 정렬되고 `/recommendations/` 화면에서 검색, 필터, 상세 확인이 가능합니다.

## 주요 API

```text
GET  /api/heartbeat
GET  /api/hsportal/info
GET  /api/hsportal/crawl-status
GET  /api/hsportal/programs
GET  /api/hsportal/programs/{program_id}
POST /api/timetable/extract
POST /api/recommendations
```

### `POST /api/timetable/extract`

`multipart/form-data`로 시간표 이미지를 전송합니다. 지원 형식은 JPEG, PNG, WEBP입니다.

```text
file=<시간표 이미지>
```

응답은 추천 API에서 그대로 사용할 수 있는 시간표 JSON입니다.

```json
{
  "courses": [
    {
      "course_name": "자료구조",
      "day_of_week": "FRI",
      "start_time": "09:00",
      "end_time": "10:30"
    }
  ],
  "warnings": []
}
```

### `POST /api/recommendations`

저장된 비교과 프로그램 데이터와 시간표를 비교합니다.

```json
{
  "courses": [
    {
      "course_name": "자료구조",
      "day_of_week": "FRI",
      "start_time": "09:00",
      "end_time": "10:30"
    }
  ],
  "include_needs_review": true,
  "include_unavailable": false,
  "limit": 30
}
```

결과는 다음 세 가지 상태로 분류됩니다.

| 상태 | 의미 |
| --- | --- |
| `available` | 당일 운영 일정이 수업과 겹치지 않고 신청 가능성이 높음 |
| `needs_review` | 장기/단기 기간형, 일정 미등록, 접수 상태 불명확 등 상세 확인 필요 |
| `unavailable` | 수업 시간과 직접 충돌하거나 정원이 마감됨 |

## 추천 기준 요약

- 프로그램 일정이 모두 같은 날짜 안에서 끝나면 실제 시간대와 수업 시간을 직접 비교합니다.
- 7일 미만의 여러 날짜 기간은 `short_period`로 보고 회차별 확인이 필요하다고 판단합니다.
- 7일 이상의 긴 기간은 상시/온라인/장기 활동 가능성이 있어 `long_period`로 분류합니다.
- 일정이 없거나 형식이 잘못된 경우 추천에서 완전히 제외하지 않고 `needs_review`로 남깁니다.
- 정원이 현재 인원 이상으로 찬 프로그램은 `unavailable`로 처리합니다.
- 점수는 가용성, 신뢰도, 일정 유형, 비교과 포인트, 충돌 수를 반영합니다.

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux에서는 가상환경 활성화만 다음 명령을 사용합니다.

```bash
source .venv/bin/activate
```

## 환경 변수

```bash
copy .env.example .env
```

`.env`의 주요 값은 다음과 같습니다.

| 변수 | 설명 |
| --- | --- |
| `APP_NAME` | 서비스 이름 |
| `APP_ENV` | `dev` 또는 `prod`; dev에서는 이미지/LLM 디버그 로그가 더 자세함 |
| `LOG_LEVEL` | 콘솔 로그 레벨 |
| `HSPORTAL_CRAWL_INTERVAL_HOURS` | HS Portal 비교과 데이터 갱신 주기. 시간 단위이며 기본값은 `1` |
| `QWEN_API_KEY` | Alibaba Cloud Model Studio / DashScope API 키 |
| `QWEN_BASE_URL` | OpenAI-compatible endpoint |
| `QWEN_MODEL` | 사용할 Vision 모델명 |
| `QWEN_ENABLE_THINKING` | Qwen thinking 옵션 사용 여부 |
| `QWEN_THINKING_BUDGET` | thinking 사용 시 선택적 budget |
| `LLM_MAX_IMAGE_BYTES` | 업로드 이미지 최대 바이트 수 |

## 실행

```bash
python -m uvicorn main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`으로 접속합니다. 개발 확인용 화면은 `http://127.0.0.1:8000/test/`입니다.

## 데이터 저장

HS Portal 크롤링 결과는 실행 중 `backend/hsportal/programs.json`에 저장됩니다. 이 파일은 `.gitignore`에 포함되어 있으며, 저장소에 커밋하지 않습니다. 서버가 처음 실행되거나 수집 정책이 변경되면 다시 생성되고, 이후에는 `HSPORTAL_CRAWL_INTERVAL_HOURS` 주기마다 cursor를 확인해 필요한 데이터만 갱신합니다.

저장 JSON의 핵심 구조는 다음과 같습니다.

```text
{
  "info": {
    "schema_version": "hsportal_programs_v2",
    "filter": {
      "status": "wait",
      "label": "접수(대기)중",
      "included_statuses": ["scheduled", "open", "waiting"]
    },
    "counts": {
      "listed": 0,
      "saved": 0,
      "pages": 0
    },
    "cursor": {
      "last_checked_program_id": null,
      "last_checked_url": null
    }
  },
  "programs": []
}
```

## 품질 확인

```bash
python -m ruff check .
python -m pytest
```

테스트는 실제 Qwen API를 호출하지 않도록 fake service와 monkeypatch를 사용합니다. 외부 API 키 없이도 대부분의 회귀 테스트를 실행할 수 있습니다.
