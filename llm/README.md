# LLM

## 담당자

- 박민재 팀원

## 디렉터리 역할

`llm` 디렉터리는 시간표 이미지 인식과 LLM API 연결을 담당하는 영역입니다. 업로드된 시간표 이미지에서 요일, 시간, 강의명 등의 정보를 추출하고, 서비스에서 활용할 수 있는 JSON 형태로 정리합니다.

## 주요 작업 범위

- LLM 모델 API 연결
- 시간표 이미지 입력 및 분석 요청 구성
- 시간표에서 수업명, 요일, 시작 시간, 종료 시간 추출
- 모델 응답을 백엔드에서 사용 가능한 JSON 형식으로 변환
- 시간표 인식 결과 검증 및 예외 처리
- 비교과 프로그램 포스터 이미지에서 일정, 장소, 신청 기간 등 추출

## 연동 대상

- `backend`: 분석된 시간표 JSON 또는 포스터 JSON을 전달합니다.
- `frontend`: 직접 연동하지 않고, 백엔드를 통해 사용자 요청을 처리하는 구조를 기준으로 합니다.

## 현재 구성

- `llm/config.py`: Qwen API 키, base URL, 모델명을 환경 변수에서 읽습니다.
- `llm/qwen_client.py`: `openai` 라이브러리로 Qwen OpenAI-compatible API 클라이언트를 생성합니다.

## 사용 모델

기본 모델은 `qwen3-vl-flash`입니다. Alibaba Cloud Model Studio / DashScope의 OpenAI-compatible endpoint를 `openai` Python 라이브러리로 호출하는 구조입니다.

환경 변수는 루트의 `.env` 파일에서 관리합니다.

```text
QWEN_API_KEY=replace-with-your-api-key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3-vl-flash
```

## 현재 구현 범위

현재 `llm` 디렉터리는 실제 이미지 분석 API 라우터를 아직 제공하지 않고, 모델 호출을 위한 설정과 클라이언트 생성을 담당합니다.

- `get_qwen_client()`: `QWEN_API_KEY`, `QWEN_BASE_URL`을 사용해 OpenAI-compatible 클라이언트를 생성합니다.
- `get_qwen_model_name()`: 현재 사용할 모델명을 반환합니다.

추후 시간표 또는 포스터 이미지 분석 기능은 이 클라이언트를 사용해 JSON 응답 스키마를 고정하는 방식으로 확장합니다.
