# Tests

## 디렉터리 역할

`tests` 디렉터리는 API, 추천 알고리즘, LLM 내부 처리 로직을 검증하는 pytest 테스트를 관리합니다.

## 현재 구성

- `tests/test_timetable_api.py`: `/api/timetable/extract` API의 성공 응답, dev/prod 이미지 디버그 로그 설정, 이미지 오류, LLM 오류 처리를 검증합니다.
- `tests/test_recommendation_api.py`: 추천 알고리즘의 일정 분류, 시간표 충돌 검사, `/api/recommendations` API 응답을 검증합니다.
- `tests/test_llm_internal.py`: 이미지 WebP 정규화, 요일/시간 정규화, LLM JSON 파싱, provider 오류 메시지 정리를 검증합니다.

## 실행

루트 디렉터리에서 실행합니다.

```bash
python -m pytest
```

코드 스타일 검사는 별도로 실행합니다.

```bash
python -m ruff check .
```

## 테스트 정책

테스트는 실제 Qwen API를 호출하지 않습니다. 외부 API 호출이 필요한 부분은 fake service 또는 monkeypatch로 대체합니다. 따라서 `QWEN_API_KEY` 없이도 대부분의 단위 테스트를 실행할 수 있습니다.
