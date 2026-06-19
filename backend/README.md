# Backend

`backend`는 서비스의 API와 도메인 로직을 담당합니다. FastAPI 애플리케이션의 진입점은 루트의 `main.py`이며, 이 디렉터리는 라우터, 추천 알고리즘, HS Portal 데이터 수집/저장 로직을 제공합니다.

## 책임 범위

- `/api` 하위 HTTP API 라우터 정의
- 서버 상태와 HS Portal 데이터 준비 상태 조회
- 시간표 이미지 분석 요청을 `llm` 계층으로 위임
- 저장된 HS Portal 비교과 프로그램 데이터 조회
- 수업 시간표와 비교과 프로그램 운영 일정 비교
- 추천 결과의 상태, 점수, 경고, 충돌 정보 구성

## 구성

```text
backend/
├─ api/
│  ├─ heartbeat.py
│  ├─ hsportal.py
│  ├─ recommendations.py
│  └─ timetable.py
├─ hsportal/
│  ├─ constants.py
│  ├─ crawler.py
│  ├─ parser.py
│  └─ storage.py
├─ config.py
└─ recommendation.py
```

## API 라우터

| 파일 | 엔드포인트 | 역할 |
| --- | --- | --- |
| `api/heartbeat.py` | `GET /api/heartbeat` | 서버 상태, 실행 환경, LLM 모델명, UTC timestamp 반환 |
| `api/timetable.py` | `POST /api/timetable/extract` | 업로드 이미지를 받아 시간표 JSON 추출 |
| `api/recommendations.py` | `POST /api/recommendations` | 시간표와 저장 프로그램을 비교해 추천 결과 반환 |
| `api/hsportal.py` | `GET /api/hsportal/*` | 저장 데이터, 메타 정보, 크롤링 상태, 단일 프로그램 조회 |

`main.py`가 위 라우터들을 `/api` prefix로 등록합니다. `backend` 안에는 별도의 FastAPI 앱 객체가 없습니다.

## 시간표 추출 API

`api/timetable.py`는 업로드 파일을 읽은 뒤 `llm.tasks.timetable.extract_timetable_from_image_bytes()`를 스레드에서 실행합니다. 오류는 성격별로 HTTP 상태 코드가 나뉩니다.

| 오류 | 상태 코드 | 의미 |
| --- | --- | --- |
| `ImagePayloadError` | `400` | 비어 있거나 지원하지 않는 이미지 |
| `LLMConfigurationError` | `503` | API 키, 모델명 등 설정 누락 |
| `LLMRequestError`, `LLMResponseParseError`, `LLMResponseValidationError` | `502` | 모델 요청 실패, JSON 파싱 실패, 스키마 검증 실패 |

`APP_ENV=dev`일 때는 이미지 정규화 디버그 로그를 남기고, `prod`에서는 동일 응답 형식을 유지하면서 상세 로그를 줄입니다.

## HS Portal 데이터 관리

HS Portal 크롤러는 `main.py`의 lifespan에서 백그라운드 주기 task로 실행됩니다. 서버 시작을 오래 막지 않도록 `asyncio.to_thread()`로 동기 크롤러를 분리하며, 시작 직후 1회 실행한 뒤 `HSPORTAL_CRAWL_INTERVAL_HOURS` 설정값에 따라 반복 실행합니다.

### 수집 정책

- 기준 URL: `https://hsportal.hansung.ac.kr`
- 목록 필터: `PROGRAM_STATUS_FILTER = "wait"`
- 포함 상태: `scheduled`, `open`, `waiting`
- 저장 파일: `backend/hsportal/programs.json`
- 상세 페이지 동시 수집 수: `DETAIL_FETCH_CONCURRENCY = 5`
- 요청 간 지연: `REQUEST_DELAY_SECONDS = 0.15`

### 수집 방식

| 상황 | 동작 |
| --- | --- |
| 저장 파일 없음 | 전체 목록과 상세 페이지를 수집 |
| 스키마 또는 필터 정책 변경 | 전체 재수집 |
| 저장 데이터 있음 | 첫 목록 페이지의 최신 프로그램 ID와 cursor 비교 |
| cursor 변경 없음 | 기존 상세 데이터는 유지하고 목록에서 확인 가능한 상태/인원/조회수만 갱신 |
| cursor 변경 있음 | cursor 전까지 새 항목만 상세 수집하고 기존 항목은 목록 정보로 갱신 |

서버 종료 시에는 crawler stop event를 설정하고 진행 중인 task를 최대 5초 기다린 뒤 필요하면 취소합니다.

## 저장 데이터 구조

`hsportal/storage.py`는 저장 파일이 없을 때도 API가 안정적으로 동작하도록 빈 데이터셋을 반환합니다.

```text
{
  "info": {
    "site": "hsportal",
    "schema_version": "hsportal_programs_v2",
    "base_url": "...",
    "list_url": "...",
    "crawled_at": "...",
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
    },
    "parser_version": "hsportal_v1"
  },
  "programs": []
}
```

각 프로그램은 `id`, `url`, `title`, `status`, `application_period`, `schedules`, `organization`, `participants`, `media`, `metrics`, `flags`, `content`, `attachments` 등을 가질 수 있습니다.

## HTML 파싱

`hsportal/parser.py`는 HS Portal 목록/상세 HTML을 구조화합니다.

- 목록 페이지: 프로그램 ID, 제목, 상태, 신청 기간, 운영 기간, 인원, 포인트, 이미지, 조회수
- 상세 페이지: 태그, 대상, 학과, 분류, 운영 부서, 연락처, 회차별 일정, 설명, 첨부파일
- 상태 객체: `code`, `label`, `badge`, `accepting`으로 분리 저장
- 기존 상세 데이터 갱신: 목록에서 확인 가능한 값만 병합하고 상세 일정은 보존

## 추천 알고리즘

`recommendation.py`는 `RecommendationRequest`와 저장 프로그램 목록을 받아 `RecommendationResponse`를 만듭니다.

### 일정 분류

| 값 | 설명 |
| --- | --- |
| `same_day` | 각 일정의 시작일과 종료일이 같은 당일 일정 |
| `short_period` | 7일 미만의 기간형 일정 |
| `long_period` | 7일 이상 장기 기간 |
| `no_schedule` | 비교할 일정 정보 없음 |
| `invalid_schedule` | 날짜/시간 파싱 불가 또는 종료가 시작보다 빠름 |

이전 코드 호환을 위해 `FIXED_SESSION`, `ASYNC_ONLINE`, `SUBMISSION` 같은 enum alias가 남아 있지만 실제 응답 값은 위 다섯 가지로 정규화됩니다.

### 가용성 판단

| 값 | 기준 |
| --- | --- |
| `available` | `same_day` 일정이고 수업과 겹치지 않으며 신청 가능성이 높음 |
| `needs_review` | 기간형, 일정 누락, 상태 불명확 등 상세 페이지 확인 필요 |
| `unavailable` | 수업과 직접 충돌하거나 현재 인원이 정원 이상 |

점수는 가용성, 신뢰도, 일정 유형, 비교과 포인트, 충돌 수를 반영합니다. 응답은 가용성 우선순위, 점수 내림차순, 제목순으로 정렬됩니다.

## 실행

루트 디렉터리에서 실행합니다.

```bash
python -m uvicorn main:app --reload
```

## 테스트 관점

`tests/test_timetable_api.py`는 이미지 업로드 API의 성공/실패 경로를 검증하고, `tests/test_recommendation_api.py`는 추천 분류와 API 응답을 검증합니다. 실제 Qwen 호출은 테스트에서 monkeypatch로 대체합니다.
