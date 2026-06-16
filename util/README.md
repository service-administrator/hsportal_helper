# Util

## 디렉터리 역할

`util` 디렉터리는 특정 도메인에 속하지 않는 공통 유틸리티를 관리합니다.

## 현재 구성

- `util/logging_config.py`: 애플리케이션 전역 콘솔 로그 형식과 로그 레벨을 설정합니다.
- `util/image_processing.py`: VLM 입력용 이미지 검증, 해상도 제한, WebP 변환을 담당합니다.

## 연동 대상

- `main.py`: FastAPI 애플리케이션 생성 시 `configure_logging()`을 호출합니다.
- `backend/config.py`: `.env`의 `LOG_LEVEL` 값을 읽어 로그 레벨로 전달합니다.

## 로그 설정

`.env` 파일에서 로그 레벨을 조정할 수 있습니다.

```text
LOG_LEVEL=INFO
```

로그 형식은 시간, 레벨, 로거 이름, 메시지를 포함합니다.

## 이미지 변환

시간표 이미지처럼 VLM에 전달되는 파일은 `util/image_processing.py`에서 WebP 형식으로 통일합니다. 긴 변은 `NORMALIZED_IMAGE_MAX_EDGE` 값인 2000px을 넘지 않도록 축소하고, EXIF 회전 보정과 RGB 변환을 함께 수행합니다.
