# Frontend

## 담당자

- 조민규 팀원

## 디렉터리 역할

`frontend` 디렉터리는 사용자가 직접 이용하는 화면을 구성하는 영역입니다. 시간표 이미지 업로드, 추천 결과 확인, 비교과 프로그램 목록 조회 등 서비스의 주요 사용자 경험을 담당합니다.

## 주요 작업 범위

- 시간표 이미지 업로드 화면 구성
- 비교과 프로그램 추천 결과 화면 구성
- 사용자의 입력 및 요청을 백엔드 API와 연결
- 추천 결과를 보기 쉽게 표현하는 UI 구성
- 서비스 전체 화면 흐름 및 사용자 인터랙션 구현

## 연동 대상

- `backend`: 시간표 분석 결과와 추천 비교과 프로그램 데이터를 요청합니다.
- `llm`: 직접 호출하지 않고, 백엔드를 통해 정리된 시간표 분석 결과를 전달받는 구조를 기준으로 합니다.

## 현재 구성

- `frontend/public/index.html`: FastAPI가 직접 제공하는 기본 HTML 화면입니다.
- `frontend/public/styles.css`: 기본 화면 스타일입니다.
- `frontend/public/app.js`: `/api/heartbeat`를 호출해 백엔드 연결 상태를 확인합니다.
- `frontend/public/test/`: 시간표 이미지를 업로드해 `/api/timetable/extract` 응답 JSON을 확인하고, 해당 JSON으로 `/api/recommendations` 추천 결과를 확인하는 테스트 화면입니다.

FastAPI 서버는 `frontend/public` 디렉터리를 정적 파일 경로로 사용합니다. 따라서 프론트엔드 HTML, CSS, JS 파일은 이 디렉터리 안에서 관리합니다.

## 실행 구조

프론트엔드는 별도 개발 서버를 사용하지 않습니다. 루트 `main.py`가 `frontend/public`을 정적 파일로 mount하므로, FastAPI 서버를 실행하면 같은 주소에서 프론트엔드와 API를 함께 사용할 수 있습니다.

```bash
python -m uvicorn main:app --reload
```

브라우저 접속 주소는 `http://127.0.0.1:8000`입니다.

## 현재 화면 동작

기본 화면은 다음 흐름으로 동작합니다.

1. `index.html`이 로드됩니다.
2. `app.js`가 `/api/heartbeat`를 호출합니다.
3. 응답이 정상이면 연결 상태를 초록색 점과 `qwen3-vl-flash` 모델명으로 표시합니다.
4. API 호출에 실패하면 연결 실패 메시지를 표시합니다.

시간표 JSON 변환 및 비교과 추천 테스트 화면은 `http://127.0.0.1:8000/test/`에서 확인합니다.

테스트 화면의 동작은 다음과 같습니다.

1. PNG, JPG, WEBP 시간표 이미지를 선택하고 미리보기를 표시합니다.
2. `JSON 변환` 버튼으로 `/api/timetable/extract`를 호출합니다.
3. 모델 응답 JSON을 textarea에 표시하고 복사할 수 있습니다.
4. `샘플` 버튼으로 API 키 없이 추천 API만 확인할 수 있는 샘플 시간표를 입력합니다.
5. `추천 실행` 버튼으로 `/api/recommendations`를 호출하고 추천 카드 목록을 표시합니다.
