# API 명세

서비스의 API는 모두 FastAPI 서버의 `/api` 하위 경로에서 제공됩니다. 프론트엔드는 같은 서버에서 정적 파일로 제공되며, 별도의 프론트엔드 개발 서버를 사용하지 않습니다.

## 엔드포인트 요약

```text
GET  /api/heartbeat
GET  /api/hsportal/info
GET  /api/hsportal/crawl-status
GET  /api/hsportal/programs
GET  /api/hsportal/programs/{program_id}
POST /api/timetable/extract
POST /api/recommendations
```

## `GET /api/heartbeat`

서버 상태, 실행 환경, LLM 모델명, UTC timestamp를 반환합니다. 프론트엔드는 이 응답의 `environment` 값을 사용해 개발용 JSON 직접 입력 버튼 표시 여부를 결정합니다.

### 응답 예시

```json
{
  "status": "ok",
  "service": "hsportal-helper",
  "environment": "dev",
  "llm_model": "qwen3-vl-plus",
  "timestamp": "2026-06-19T05:30:00+00:00"
}
```

## `GET /api/hsportal/info`

저장된 HS Portal 비교과 프로그램 데이터의 메타 정보를 반환합니다. 수집 시각, 수집 정책, 저장 개수, cursor 정보 등을 확인할 수 있습니다.

## `GET /api/hsportal/crawl-status`

서버 시작 후 백그라운드에서 실행되는 HS Portal 크롤러의 현재 상태를 반환합니다.

### 주요 상태

| 상태 | 의미 |
| --- | --- |
| `scheduled` | 크롤링 작업 예약됨 |
| `running` | 비교과 데이터 수집/갱신 중 |
| `ready` | 비교과 데이터 준비 완료 |
| `failed` | 데이터 준비 실패 |
| `cancelled` | 서버 종료 등으로 작업 중단 |
| `unknown` | 상태 정보 없음 |

### 응답 예시

```json
{
  "status": "ready",
  "message": "HS Portal program data is ready.",
  "last_started_at": "2026-06-19T14:00:00+09:00",
  "last_finished_at": "2026-06-19T14:00:12+09:00",
  "next_run_at": "2026-06-19T15:00:12+09:00",
  "interval_hours": 1
}
```

## `GET /api/hsportal/programs`

저장된 비교과 프로그램 전체 데이터셋을 반환합니다. 응답에는 `info` 메타 정보와 `programs` 배열이 포함됩니다.

## `GET /api/hsportal/programs/{program_id}`

특정 비교과 프로그램의 상세 정보를 반환합니다. `program_id`와 일치하는 프로그램이 없으면 `404`를 반환합니다.

## `POST /api/timetable/extract`

시간표 이미지를 업로드하면 Vision LLM을 통해 수업 목록 JSON을 추출합니다. 업로드 파일은 서버에서 이미지 형식을 검증하고 WebP로 정규화한 뒤 LLM 요청 payload로 변환합니다.

### 요청

`multipart/form-data` 형식으로 이미지를 전송합니다.

```text
file=<시간표 이미지>
```

지원 형식은 JPEG, PNG, WEBP입니다.

### 응답 예시

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

### 오류

| 오류 | 상태 코드 | 의미 |
| --- | --- | --- |
| `ImagePayloadError` | `400` | 비어 있거나 지원하지 않는 이미지 |
| `LLMConfigurationError` | `503` | API 키, 모델명 등 설정 누락 |
| `LLMRequestError` | `502` | LLM provider API 요청 실패 |
| `LLMResponseParseError` | `502` | LLM 응답에서 JSON을 파싱할 수 없음 |
| `LLMResponseValidationError` | `502` | LLM JSON 응답이 기대 스키마와 맞지 않음 |

## `POST /api/recommendations`

저장된 비교과 프로그램 데이터와 시간표를 비교하여 추천 결과를 반환합니다.

### 요청 예시

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

### 요청 필드

| 필드 | 설명 |
| --- | --- |
| `courses` | 수업 목록. 요일은 `MON`~`SUN`, 시간은 `HH:MM` 형식 |
| `include_needs_review` | `확인 필요` 결과 포함 여부 |
| `include_unavailable` | `참여 불가` 결과 포함 여부 |
| `limit` | 반환 개수. 1~100 사이 값 |

### 응답 주요 필드

| 필드 | 설명 |
| --- | --- |
| `recommendations` | 추천 결과 배열 |
| `counts.available` | 전체 평가 결과 중 참여 가능 개수 |
| `counts.needs_review` | 전체 평가 결과 중 확인 필요 개수 |
| `counts.unavailable` | 전체 평가 결과 중 참여 불가 개수 |
| `counts.returned` | 필터와 limit 적용 후 실제 반환 개수 |
| `counts.total` | 평가한 전체 프로그램 개수 |
| `warnings` | 전체 응답 수준의 경고 |

### 추천 결과 필드

| 필드 | 설명 |
| --- | --- |
| `program_id` | HS Portal 프로그램 ID |
| `title` | 프로그램명 |
| `url` | 프로그램 상세 페이지 URL |
| `category` | 프로그램 분류 |
| `schedule_kind` | 일정 유형 |
| `availability` | `available`, `needs_review`, `unavailable` |
| `confidence` | 판단 신뢰도. `high`, `medium`, `low` |
| `score` | 정렬에 사용하는 추천 점수 |
| `matched_reason` | 해당 상태로 분류한 이유 |
| `warnings` | 프로그램별 확인 사항 |
| `conflicts` | 수업과 직접 충돌한 시간 정보 |
| `program` | 원본 프로그램 데이터 |
