# Tests

`tests`는 API 라우터, 추천 알고리즘, LLM 내부 처리, 이미지 정규화 규칙을 검증하는 pytest 테스트 모음입니다. 실제 Qwen API를 호출하지 않도록 fake service와 monkeypatch를 사용합니다.

## 구성

```text
tests/
├─ test_timetable_api.py
├─ test_recommendation_api.py
└─ test_llm_internal.py
```

## 파일별 검증 범위

| 파일 | 검증 내용 |
| --- | --- |
| `test_timetable_api.py` | `/api/timetable/extract` 성공 응답, dev/prod 디버그 옵션, 잘못된 이미지 처리, LLM 오류의 HTTP 변환과 로그 |
| `test_recommendation_api.py` | 일정 유형 분류, 수업 시간 충돌, 기간형 프로그램 판단, 저장 데이터 기반 추천 API 응답 |
| `test_llm_internal.py` | 이미지 WebP 정규화, 요일/시간 정규화, fenced JSON 파싱, provider 오류 메시지 정리, dev LLM 응답 로그, Qwen thinking 옵션 |

## 실행

루트 디렉터리에서 실행합니다.

```bash
python -m pytest
```

정적 검사도 함께 확인합니다.

```bash
python -m ruff check .
```

## 테스트 설계 원칙

- 외부 네트워크 호출을 하지 않습니다.
- 실제 Qwen API 키가 없어도 실행 가능해야 합니다.
- FastAPI 라우터는 필요한 라우터만 포함한 작은 테스트 앱으로 검증합니다.
- 환경 변수 기반 설정은 테스트에서 변경 후 cache를 비웁니다.
- 이미지 테스트는 Pillow로 메모리 PNG를 생성해 파일 의존성을 없앱니다.

## 주요 fake 객체

- `test_timetable_api.py`는 `extract_timetable_from_image_bytes()`를 monkeypatch해 API 라우터의 HTTP 동작만 검증합니다.
- `test_recommendation_api.py`는 `load_dataset()`을 monkeypatch해 저장 파일 없이 추천 API를 검증합니다.
- `test_llm_internal.py`는 `_FakeLLMService`, `_FakeOpenAIClient`, `_FakeAPIError`로 LLM 내부 흐름을 검증합니다.

## 현재 보장하는 회귀

- dev 환경에서는 시간표 이미지 디버그 로그가 켜지고 prod에서는 꺼집니다.
- LLM provider 오류는 traceback 없이 사용 가능한 메시지로 API 응답에 변환됩니다.
- 작은 이미지는 최소 edge 기준으로 확대되고 큰 이미지는 최대 edge 기준으로 축소됩니다.
- 모델 응답이 markdown code fence를 포함해도 JSON object를 추출할 수 있습니다.
- 수업과 같은 요일/시간대에 겹치는 당일 비교과 일정은 `unavailable`로 분류됩니다.
- 장기 기간형, 일정 누락형 프로그램은 자동 탈락시키지 않고 `needs_review`로 남깁니다.
