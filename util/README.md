# Util

`util`은 특정 도메인에 묶이지 않는 공통 기능을 보관합니다. 현재는 앱 전역 로깅 설정과 Vision 모델 입력용 이미지 전처리를 담당합니다.

## 구성

```text
util/
├─ logging_config.py
└─ image_processing.py
```

## `logging_config.py`

`configure_logging()`은 FastAPI 앱 생성 시 한 번 호출됩니다.

- 루트 로거 handler를 초기화하고 stdout handler를 등록합니다.
- 로그 레벨은 `.env`의 `LOG_LEVEL`에서 전달됩니다.
- 로그 형식은 시간, 레벨, 로거 이름, 메시지를 포함합니다.
- `httpx`, `httpcore` 로거는 `WARNING`으로 낮춰 크롤링/LLM 요청 로그가 과도해지지 않게 합니다.

```text
HH:MM:SS | INFO     | logger.name | message
```

연동 위치:

- `main.py`: 앱 시작 시 `configure_logging(settings.log_level)` 호출
- `backend.config`: `.env`에서 `LOG_LEVEL` 읽기

## `image_processing.py`

시간표 이미지를 Vision 모델에 넣기 전에 검사하고 정규화합니다.

### 입력 검사

`inspect_image()`는 Pillow로 이미지를 열어 다음 정보를 반환합니다.

- 원본 포맷
- MIME type
- width
- height

지원 형식은 다음 세 가지입니다.

| 포맷 | MIME |
| --- | --- |
| JPEG | `image/jpeg` |
| PNG | `image/png` |
| WEBP | `image/webp` |

지원하지 않는 형식이거나 손상된 파일이면 `ValueError`를 발생시킵니다.

### 정규화

`normalize_image_for_vlm()`은 모델 입력 품질을 일정하게 만들기 위해 다음 작업을 수행합니다.

1. EXIF 회전 정보를 반영합니다.
2. 투명도가 있는 이미지는 흰 배경으로 합성합니다.
3. RGB가 아닌 이미지는 RGB로 변환합니다.
4. 가장 긴 변이 1500px보다 작으면 확대하고, 2500px보다 크면 축소합니다.
5. WebP 형식으로 저장합니다.

현재 상수:

```text
NORMALIZED_IMAGE_MIN_EDGE=1500
NORMALIZED_IMAGE_MAX_EDGE=2500
NORMALIZED_IMAGE_FORMAT=WEBP
NORMALIZED_IMAGE_MIME_TYPE=image/webp
WEBP_QUALITY=92
```

## 연동 관계

| 호출 주체 | 사용 기능 |
| --- | --- |
| `llm.media.prepare_image_data_url()` | 이미지 검사와 WebP 정규화 |
| `llm.tasks.timetable` | dev 로그에 원본/정규화 이미지 크기 기록 |
| `tests/test_llm_internal.py` | 이미지 정규화 규칙 회귀 테스트 |

## 주의 사항

- 이 모듈은 HTTP 업로드 크기 제한을 판단하지 않습니다. 바이트 제한은 `llm.media`에서 `LLM_MAX_IMAGE_BYTES`로 처리합니다.
- 최소 변이 아니라 가장 긴 변 기준으로 확대/축소합니다.
- WebP 변환은 LLM 요청 payload를 줄이고 포맷을 통일하기 위한 내부 처리이며, 사용자가 업로드한 원본 파일을 덮어쓰지 않습니다.
