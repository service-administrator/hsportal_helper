# LLM

`llm`은 외부 Vision 모델과 통신하는 내부 서비스 계층입니다. API 라우터를 직접 제공하지 않고, `backend.api.timetable`에서 import해 사용합니다.

## 책임 범위

- Qwen OpenAI-compatible 클라이언트 생성
- 업로드 이미지 검증과 Vision 요청용 data URL 생성
- JSON 응답을 요구하는 LLM task 정의
- 모델 응답 텍스트 추출, JSON 파싱, Pydantic 검증
- 시간표 이미지에서 수업명, 요일, 시작/종료 시간 추출
- LLM 설정 오류, 요청 오류, 응답 파싱/검증 오류를 명확한 예외로 분리

## 구성

```text
llm/
├─ config.py
├─ exceptions.py
├─ media.py
├─ qwen_client.py
├─ schemas.py
├─ service.py
└─ tasks/
   ├─ base.py
   └─ timetable.py
```

## 파일별 역할

| 파일 | 역할 |
| --- | --- |
| `config.py` | `.env`에서 Qwen endpoint, 모델명, thinking 옵션, 이미지 크기 제한 읽기 |
| `qwen_client.py` | `openai.OpenAI` 클라이언트 생성과 모델명 조회 |
| `media.py` | 이미지 바이트 검증, MIME 확인, WebP 정규화 후 base64 data URL 생성 |
| `schemas.py` | 시간표 추출 결과 스키마와 요일/시간 정규화 규칙 |
| `service.py` | LLM task 실행, provider 오류 정리, 응답 JSON 파싱/검증 |
| `exceptions.py` | LLM 계층 전용 예외 타입 |
| `tasks/base.py` | 재사용 가능한 JSON task와 Vision image dataclass |
| `tasks/timetable.py` | 시간표 추출 system instruction, prompt, Qwen extra body 구성 |

## 환경 변수

```text
QWEN_API_KEY=replace-with-your-api-key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3-vl-flash
QWEN_ENABLE_THINKING=false
# QWEN_THINKING_BUDGET=1024
LLM_MAX_IMAGE_BYTES=10485760
APP_ENV=dev
```

- `QWEN_API_KEY`가 없으면 `LLMConfigurationError`가 발생합니다.
- `APP_ENV=dev`에서는 LLM API 응답 전체를 로그로 남겨 디버깅을 돕습니다.
- `QWEN_ENABLE_THINKING`과 `QWEN_THINKING_BUDGET`은 Qwen extra body에 전달됩니다.
- `LLM_MAX_IMAGE_BYTES`는 원본 업로드 바이트 크기 제한입니다.

## 시간표 추출 흐름

1. `backend.api.timetable`이 업로드 이미지 bytes와 content type을 전달합니다.
2. `media.prepare_image_data_url()`이 이미지가 비어 있지 않은지, 크기 제한을 넘지 않는지, MIME이 실제 파일과 일치하는지 확인합니다.
3. `util.image_processing.normalize_image_for_vlm()`이 EXIF 회전 보정, RGB 변환, 크기 조정, WebP 변환을 수행합니다.
4. `tasks.timetable.build_timetable_extraction_task()`가 prompt와 image data URL을 가진 `LLMJSONTask`를 만듭니다.
5. `LLMService.run_json_task()`가 Qwen OpenAI-compatible Chat Completions API를 호출합니다.
6. 응답 본문에서 텍스트를 추출하고 JSON object를 파싱합니다.
7. `TimetableExtractionResult`로 검증해 `courses`와 `warnings`를 반환합니다.

## 시간표 스키마

```json
{
  "courses": [
    {
      "course_name": "자료구조",
      "day_of_week": "MON",
      "start_time": "09:00",
      "end_time": "10:30"
    }
  ],
  "warnings": []
}
```

### 정규화 규칙

- 요일은 `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`으로 정규화합니다.
- `월`, `월요일`, `MONDAY` 같은 alias를 허용합니다.
- 시간은 `9:00`, `10시 30분` 같은 입력을 `HH:MM`으로 정규화합니다.
- 종료 시간이 시작 시간보다 늦지 않으면 검증 오류가 발생합니다.
- 응답에 정의되지 않은 추가 필드는 무시합니다.

## 이미지 처리 기준

실제 이미지 전처리는 `util.image_processing`에서 담당하고, `llm.media`는 LLM 요청 payload로 포장합니다.

- 입력 허용: JPEG, PNG, WEBP
- 출력 형식: WebP
- 가장 긴 변 목표 범위: 1500px 이상, 2500px 이하
- WebP 품질: 92
- Vision 요청 payload: `data:image/webp;base64,...`

## 오류 처리

| 예외 | 발생 상황 | API 변환 |
| --- | --- | --- |
| `ImagePayloadError` | 이미지 누락, 크기 초과, MIME 불일치, 지원하지 않는 포맷 | `400` |
| `LLMConfigurationError` | API 키 또는 모델 설정 누락 | `503` |
| `LLMRequestError` | provider API 요청 실패 | `502` |
| `LLMResponseParseError` | 응답에서 JSON object를 파싱할 수 없음 | `502` |
| `LLMResponseValidationError` | JSON이 기대 스키마와 맞지 않음 | `502` |

## 확장 방법

새로운 LLM 작업은 `llm/tasks/`에 task builder를 추가하고 `LLMService.run_json_task()`를 재사용하는 방식으로 확장합니다. 응답 모델은 Pydantic `BaseModel`로 정의하고, 외부 API 라우터에서는 `llm` 내부 예외를 HTTP 오류로 변환합니다.
