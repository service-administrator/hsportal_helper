# 비교과 프로그램 추천 서비스

대학교 비교과 프로그램 정보를 수집하고, 학생의 시간표 이미지를 분석하여 참여 가능한 비교과 프로그램을 추천하는 웹 서비스입니다. 사용자는 자신의 시간표 이미지를 업로드하고, 서비스는 LLM Vision 모델을 활용해 시간표 데이터를 JSON 형태로 추출한 뒤 비어 있는 시간대와 비교과 프로그램 일정을 비교하여 적합한 프로그램을 추천합니다.

## 프로젝트 목적

대학생은 학업, 아르바이트, 동아리, 개인 일정 등으로 인해 비교과 프로그램을 직접 찾아보고 자신의 시간표와 맞는지 확인하는 데 많은 시간을 사용합니다. 이 프로젝트는 학교 비교과 프로그램 사이트에서 수집한 프로그램 정보를 바탕으로, 학생의 실제 시간표와 충돌하지 않는 프로그램을 자동으로 추천하는 것을 목표로 합니다.

이를 통해 학생은 참여 가능한 프로그램을 더 쉽게 발견할 수 있고, 학교는 비교과 프로그램 참여율을 높일 수 있습니다.

## 주요 기능

- 대학교 비교과 프로그램 사이트 크롤링
- 시간표 이미지 업로드 및 전처리
- LLM Vision 모델을 활용한 시간표 데이터 추출
- 시간표 데이터를 JSON 형태로 구조화
- 학생의 빈 시간대와 비교과 프로그램 일정 비교
- 시간표에 맞는 비교과 프로그램 추천

## 프로젝트 구조

```text
/
├── main.py
│   └── FastAPI 애플리케이션 진입점
├── frontend/
│   └── public/
│       └── HTML, CSS, JS 정적 프론트엔드 파일
├── backend/
│   ├── api/
│   │   └── 서버 상태, 시간표 분석, 추천, 비교과 프로그램 조회 API
│   ├── recommendation.py
│   │   └── 시간표와 비교과 일정 충돌 검사 및 추천 점수 계산
│   └── hsportal/
│       └── 비교과 프로그램 크롤링, 파싱, JSON 저장 로직
├── llm/
│   └── LLM API 연결 및 시간표 인식 로직 구성
├── util/
│   └── 프로그램 전역 공통 유틸리티 구성
└── tests/
    └── API, 추천 알고리즘, LLM 내부 처리 테스트
```

## 디렉터리 역할

### `frontend`

사용자가 시간표 이미지를 업로드하고 추천 결과를 확인할 수 있는 화면을 구성합니다. 현재는 `frontend/public`의 정적 HTML, CSS, JS 파일을 루트 `main.py`에서 제공합니다. 기본 화면은 `/api/heartbeat`를 호출해 서버 연결 상태를 확인하고, `/test/` 화면은 시간표 이미지 JSON 변환과 비교과 추천 API를 함께 확인합니다.

### `backend`

시간표 데이터와 비교과 프로그램 데이터를 처리하고, 추천 알고리즘을 실행하는 백엔드 API를 구성합니다. 현재는 `/api/heartbeat`, `/api/timetable/extract`, `/api/recommendations`, `/api/hsportal/*` API와 한성대학교 비교과 프로그램 크롤러, 파서, JSON 저장 로직을 포함합니다.

### `llm`

시간표 이미지 또는 비교과 프로그램 포스터에서 요일, 시간, 강의명, 일정 등의 정보를 추출하기 위한 LLM API 연결부를 구성합니다. 현재는 OpenAI-compatible 방식으로 Qwen API 클라이언트, 이미지 입력 변환, JSON 응답 검증, 시간표 추출 task를 제공합니다. 외부 API 라우터로 직접 노출하지 않고 `backend` 내부 코드에서 import해 사용하는 구조입니다.

### `util`

특정 도메인에 속하지 않는 공통 유틸리티를 관리합니다. 현재는 프로그램 실행 시 콘솔 로그 형식과 로그 레벨을 설정하는 로거 설정을 담당합니다.

### `tests`

시간표 이미지 API, 추천 API, LLM 내부 JSON 파싱/검증/이미지 정규화 동작을 검증하는 pytest 테스트를 관리합니다. 외부 Qwen API는 테스트에서 직접 호출하지 않고 fake service 또는 monkeypatch로 대체합니다.

## 역할 분담

| 이름 | 담당 영역 |
| --- | --- |
| 조민규 팀원 | 프론트엔드 구성 |
| 박민재 팀원 | 비교과 프로그램 크롤러 및 시간표 인식을 위한 LLM API 연결 |
| 김민준 팀원 | 비교과 프로그램 추천 알고리즘 및 백엔드 API 구성 |

## 데이터 처리 흐름

1. 루트 `main.py`가 FastAPI 앱을 실행하고 `frontend/public` 정적 파일과 `backend` API 라우터를 함께 등록합니다.
2. 서버가 먼저 시작된 뒤 백그라운드 작업으로 한성대학교 비교과 프로그램 데이터를 확인합니다.
3. 저장 데이터가 없으면 한성대학교 비교과프로그램 `전체` 목록에서 `접수(대기)중` 필터에 포함되는 프로그램을 전체 수집합니다.
4. 저장 데이터가 있으면 목록 첫 페이지를 확인하고, 첫 프로그램 ID가 저장된 cursor와 다를 때만 새 프로그램을 증분 수집합니다.
5. 기존 프로그램은 목록 페이지에서 확인 가능한 상태, 신청자 수, 조회 수 중심으로 갱신하고, 새 프로그램만 상세 페이지를 열어 세부 정보를 수집합니다.
6. 사용자가 자신의 시간표 이미지를 업로드합니다.
7. LLM Vision 모델이 시간표 이미지에서 수업 정보를 추출합니다.
8. 추출된 시간표 정보를 `courses`, `warnings` 형태의 JSON 데이터로 검증합니다.
9. `/api/recommendations`가 학생의 수업 시간과 저장된 비교과 프로그램 일정을 비교합니다.
10. 추천 결과를 `available`, `needs_review`, `unavailable`로 분류하고 점수순으로 제공합니다.

## 기대 효과

- 학생의 비교과 프로그램 탐색 시간 단축
- 개인 시간표에 맞는 프로그램 추천으로 참여 가능성 향상
- 비교과 프로그램 정보 접근성 개선
- 학교 비교과 활동 참여 활성화

## 실행 환경 설정

이 프로젝트는 루트의 `main.py`를 진입점으로 사용하며, 하나의 Python FastAPI 프로세스에서 프론트엔드 정적 파일, 백엔드 API, 내부 LLM API 연동을 함께 실행합니다.

### 설치

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux 환경에서는 가상환경 활성화 명령만 아래처럼 실행합니다.

```bash
source .venv/bin/activate
```

### 환경 변수

```bash
copy .env.example .env
```

`.env` 파일의 `QWEN_API_KEY` 값에 Alibaba Cloud Model Studio 또는 DashScope에서 발급받은 API 키를 입력합니다.
`.env` 파일의 `APP_ENV` 값은 개발 환경에서는 `dev`, 운영 환경에서는 `prod`로 설정합니다.
실행 로그의 상세도는 `.env` 파일의 `LOG_LEVEL` 값으로 조정할 수 있습니다. 기본값은 `INFO`입니다.
이미지 업로드 크기 제한은 `.env` 파일의 `LLM_MAX_IMAGE_BYTES` 값으로 조정할 수 있습니다.

### 실행

```bash
python -m uvicorn main:app --reload
```

실행 후 브라우저에서 `http://127.0.0.1:8000`으로 접속합니다.

### 기본 확인 API

```text
GET /api/heartbeat
```

서버 상태, 실행 환경, 사용 예정 LLM 모델 이름을 JSON으로 반환합니다.

응답 예시는 다음과 같습니다.

```json
{
  "status": "ok",
  "service": "hsportal-helper",
  "environment": "dev",
  "llm_model": "qwen3-vl-flash",
  "timestamp": "2026-06-16T12:00:00+00:00"
}
```

### 시간표 이미지 JSON 변환 테스트

시간표 이미지 분석은 `backend` API를 통해 호출할 수 있습니다. 이 API는 VLM 호출 결과를 JSON으로 변환해 반환하며, 추천 기능 구현 시에도 같은 내부 `llm` 모듈을 사용합니다.

```text
POST /api/timetable/extract
Content-Type: multipart/form-data
file=<시간표 이미지>
```

테스트 화면은 FastAPI 서버 실행 후 아래 주소에서 확인할 수 있습니다.

```text
http://127.0.0.1:8000/test/
```

`APP_ENV=dev`일 때는 서버 콘솔 로그에 원본 이미지와 WebP 정규화 이미지의 MIME, 용량, 해상도, 최대 변 길이, LLM API 응답 객체 전체가 출력됩니다. API 응답 형식은 `dev`, `prod` 모두 동일합니다.

### 비교과 추천 API

저장된 `backend/hsportal/programs.json` 데이터와 시간표 JSON을 비교해 추천 결과를 반환합니다.

```text
POST /api/recommendations
Content-Type: application/json
```

요청 예시는 다음과 같습니다.

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

추천 결과는 일정 충돌이 없는 `available`, 장기/불명확 일정이라 상세 확인이 필요한 `needs_review`, 수업과 겹치거나 정원이 마감된 `unavailable`로 분류됩니다.

### 비교과 프로그램 데이터

비교과 프로그램 크롤링은 외부 API로 실행하지 않습니다. 서버가 먼저 시작된 뒤 백그라운드 작업으로 내부 크롤러가 `backend/hsportal/programs.json` 존재 여부를 확인합니다. 저장 데이터가 있으면 매 시작마다 목록 첫 페이지를 한 번만 확인해 `info.cursor.last_checked_program_id`와 비교하고, cursor가 바뀐 경우에만 새 프로그램을 증분 수집합니다. 이 필터에는 접수예정 프로그램도 포함될 수 있습니다. 서버 종료 시에는 백그라운드 크롤러에 중단 신호를 보내 진행 중인 요청 이후 작업을 멈춥니다.

`backend/hsportal/programs.json`은 실행 중 생성되는 크롤링 결과 파일이며 Git 추적 대상에서 제외합니다. 교수님 채점 환경에서는 서버 첫 실행 시 백그라운드 크롤링으로 다시 생성됩니다.

```text
GET /api/hsportal/info
GET /api/hsportal/crawl-status
GET /api/hsportal/programs
GET /api/hsportal/programs/{program_id}
```

수집 정책은 `backend/hsportal/constants.py`에서 조정합니다.

- `PROGRAM_STATUS_FILTER`: 수집할 접수 상태입니다. 기본값은 `접수(대기)중`을 의미하는 `wait`입니다.
- `DETAIL_FETCH_CONCURRENCY`: 상세 페이지를 동시에 크롤링할 개수입니다.

저장 JSON의 `info`에는 수집 기준과 개수를 묶어서 기록합니다. `info.filter`에는 포털 필터 값과 포함 상태가 들어가고, `info.counts`에는 포털 목록에서 확인한 개수 `listed`, 실제 저장한 개수 `saved`, 페이지 수 `pages`가 들어갑니다. 다음 증분 수집 기준은 `info.cursor.last_checked_program_id`입니다.

각 프로그램의 `status`는 문자열이 아니라 객체로 저장합니다. 접수예정처럼 아직 신청할 수 없는 프로그램이 섞일 수 있기 때문에 `code`, `label`, `badge`, `accepting`을 분리해 저장합니다. `badge`는 `D-12`, `임박`처럼 목록 화면 표시가 따로 있을 때만 사용합니다.

### 코드 품질 확인

```bash
python -m ruff check .
python -m pytest
```

테스트는 `tests/` 디렉터리에서 관리합니다. 기본 동작은 `/api/heartbeat`, `/api/timetable/extract`, `/api/hsportal/crawl-status`, `/api/hsportal/programs` 응답으로도 확인합니다.
