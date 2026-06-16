# Backend

## 담당자

- 박민재/김민준 팀원

## 디렉터리 역할

`backend` 디렉터리는 시간표 데이터와 비교과 프로그램 데이터를 처리하고, 학생의 일정에 맞는 비교과 프로그램을 추천하는 API를 구성하는 영역입니다.

## 주요 작업 범위

- 프론트엔드 요청을 처리하는 백엔드 API 구성
- LLM에서 추출된 시간표 JSON 데이터 처리
- 크롤링된 비교과 프로그램 데이터 저장 및 조회
- 학생의 수업 시간과 비교과 프로그램 일정 비교
- 참여 가능한 비교과 프로그램 추천 알고리즘 구현
- 추천 결과를 프론트엔드에 전달하는 응답 형식 정의

## 연동 대상

- `frontend`: 시간표 업로드 요청과 추천 결과 조회 요청을 처리합니다.
- `llm`: 시간표 이미지 분석 결과를 내부 코드로 받아 추천 알고리즘에 활용합니다.

## 현재 구성

- `backend/config.py`: 백엔드 실행 환경을 관리합니다.
- `backend/api/heartbeat.py`: 서버 상태 확인용 `/api/heartbeat` API를 제공합니다.
- `backend/api/hsportal.py`: 저장된 비교과 프로그램 데이터를 읽는 `/api/hsportal` API를 제공합니다.
- `backend/api/timetable.py`: 시간표 이미지를 VLM으로 분석해 JSON으로 반환하는 `/api/timetable/extract` API를 제공합니다.
- `backend/hsportal/`: 한성대학교 비교과 프로그램 크롤링, 파싱, JSON 저장 로직을 관리합니다.

FastAPI 애플리케이션의 진입점은 루트 디렉터리의 `main.py`입니다. `backend` 디렉터리는 API 라우터와 백엔드 로직만 담당합니다.

## 실행 구조

루트 `main.py`가 `backend.api.heartbeat`, `backend.api.hsportal`, `backend.api.timetable` 라우터를 `/api` prefix로 등록합니다. `backend` 디렉터리 안에는 별도 FastAPI 진입점 파일을 두지 않습니다.

`.env`의 `APP_ENV`는 `dev` 또는 `prod`로 설정합니다. `dev` 환경에서는 `/api/timetable/extract` 처리 중 이미지 전처리 디버그 정보가 서버 콘솔 로그로 출력됩니다. API 응답 형식은 환경과 관계없이 동일합니다.

## 비교과 프로그램 데이터 관리

비교과 프로그램 크롤링은 외부 API로 직접 실행하지 않습니다. FastAPI 서버가 먼저 시작된 뒤 백그라운드 작업으로 저장된 프로그램 데이터가 있는지 확인합니다. 데이터가 없으면 전체 수집을 실행하고, 데이터가 있으면 목록 첫 페이지를 한 번만 확인해 저장된 cursor와 비교합니다. 첫 프로그램 ID가 cursor와 다를 때만 새 프로그램을 증분 수집합니다. 따라서 크롤링 시간이 길어도 `Waiting for application startup` 단계에서 서버 실행이 멈춘 것처럼 보이지 않습니다.

- 저장 파일: `backend/hsportal/programs.json`
- 크롤링 대상: 한성대학교 비교과프로그램 `전체` 목록의 `접수(대기)중` 프로그램
- 수집 상태: `backend/hsportal/constants.py`의 `PROGRAM_STATUS_FILTER`
- 상세 동시 수집 개수: `backend/hsportal/constants.py`의 `DETAIL_FETCH_CONCURRENCY`
- 증분 수집 기준: `info.cursor.last_checked_program_id`

트래픽을 줄이기 위해 기존 프로그램의 상태, 신청자 수, 조회 수 같은 변동 정보는 상세 페이지를 다시 열지 않고 목록 페이지에서 확인 가능한 값만 갱신합니다. 새로 발견된 `접수(대기)중` 프로그램만 상세 페이지에 접근해 대상, 장소, 연락처, 세부내용, 첨부파일을 수집합니다. 상세 페이지는 `DETAIL_FETCH_CONCURRENCY` 개수만큼 동시에 요청해 초기 수집과 새 프로그램 수집 속도를 높입니다. 이 필터에는 접수예정 프로그램도 포함될 수 있으므로 프로그램 상태는 `status.code`, `status.label`, `status.badge`, `status.accepting`으로 분리해 저장합니다. 서버 종료 시에는 백그라운드 크롤러에 중단 신호를 전달해 다음 요청이나 대기 구간에서 즉시 빠져나오도록 합니다.

### 읽기 API

```text
GET /api/heartbeat
POST /api/timetable/extract
GET /api/hsportal/info
GET /api/hsportal/crawl-status
GET /api/hsportal/programs
GET /api/hsportal/programs/{program_id}
```

외부에서 사용할 수 있는 API는 저장된 프로그램 데이터를 읽는 기능, 백그라운드 크롤링 상태 확인 기능, 시간표 이미지 JSON 변환 테스트 기능을 제공합니다. 크롤링 실행은 `HsportalCrawler.ensure_program_data()`, `crawl_full()`, `crawl_incremental()`, `refresh_existing_from_list()` 같은 내부 메소드로만 관리합니다.

### 저장 JSON 구조

`backend/hsportal/programs.json`은 다음 형태를 기준으로 저장됩니다.

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
      "listed": 29,
      "saved": 29,
      "pages": 3
    },
    "cursor": {
      "last_checked_program_id": "13920",
      "last_checked_url": "..."
    }
  },
  "programs": []
}
```

각 프로그램은 `id`, `url`, `title`, `status`, `application_period`, `schedules`, `organization`, `participants`, `media`, `metrics`, `flags`, `content`, `attachments` 등을 포함합니다.

`status`는 문자열 하나로 저장하지 않고 아래처럼 분리합니다.

```text
{
  "code": "scheduled",
  "label": "접수예정",
  "badge": null,
  "accepting": false
}
```

### 백그라운드 크롤링 상태

서버 startup은 크롤링 완료를 기다리지 않습니다. 루트 `main.py`의 lifespan에서 `HsportalCrawler`를 생성하고 `asyncio.create_task()`로 백그라운드 작업을 예약합니다. 동기 크롤러는 `asyncio.to_thread()`에서 실행되므로 크롤링 중에도 서버는 API 요청을 받을 수 있습니다.

`GET /api/hsportal/crawl-status`는 다음 상태 중 하나를 반환합니다.

```text
scheduled
running
ready
failed
cancelled
unknown
```

서버 종료 시에는 crawler stop event를 설정하고, 진행 중인 작업을 최대 5초 동안 기다린 뒤 필요하면 task를 취소합니다.

## 실행

루트 디렉터리에서 의존성을 설치한 뒤 아래 명령으로 실행합니다.

```bash
python -m uvicorn main:app --reload
```

루트 `main.py`가 `backend`의 API 라우터를 불러오고, `frontend/public` 정적 파일을 함께 제공합니다. API 경로는 `/api` prefix를 사용합니다.
