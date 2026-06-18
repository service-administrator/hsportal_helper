# Frontend

`frontend`는 사용자가 직접 보는 정적 웹 화면을 담당합니다. 별도의 프론트엔드 빌드 도구 없이 `frontend/public`의 HTML, CSS, JavaScript를 FastAPI가 그대로 제공합니다.

## 책임 범위

- 시간표 이미지 업로드와 미리보기
- 시간표 영역 크롭
- 서버 상태와 HS Portal 데이터 준비 상태 표시
- VLM이 추출한 시간표 JSON을 브라우저에서 보관
- 시간표 블록 편집, 추가, 삭제, 충돌 확인
- 추천 API 호출과 추천 결과 표시
- 개발용 JSON 직접 입력 및 테스트 화면 제공

## 구성

```text
frontend/
└─ public/
   ├─ index.html
   ├─ app.js
   ├─ image-cropper.js
   ├─ styles.css
   ├─ timetable/
   │  ├─ index.html
   │  └─ app.js
   ├─ recommendations/
   │  ├─ index.html
   │  └─ app.js
   └─ test/
      ├─ index.html
      ├─ app.js
      └─ styles.css
```

## 화면별 역할

| 경로 | 파일 | 역할 |
| --- | --- | --- |
| `/` | `index.html`, `app.js`, `image-cropper.js` | 메인 진입, 서버 상태 확인, 이미지 업로드, 크롭, 시간표 분석 요청 |
| `/timetable/` | `timetable/index.html`, `timetable/app.js` | 추출된 수업 블록 편집, JSON 확인, 추천 API 호출 |
| `/recommendations/` | `recommendations/index.html`, `recommendations/app.js` | 추천 결과 목록, 검색/필터, 프로그램 상세 모달 |
| `/test/` | `test/index.html`, `test/app.js`, `test/styles.css` | 개발용 시간표 추출/추천 API 수동 확인 |

## 사용자 흐름

1. `/`에서 `/api/heartbeat`와 `/api/hsportal/crawl-status`를 호출해 서버 상태를 표시합니다.
2. 사용자가 PNG, JPG, WEBP 시간표 이미지를 선택합니다.
3. `image-cropper.js`가 시간표 영역 선택 UI를 열고, 적용 시 브라우저에서 크롭 이미지를 생성합니다.
4. `app.js`가 `/api/timetable/extract`로 이미지를 전송합니다.
5. 응답받은 시간표 JSON과 원본 파일 정보를 `sessionStorage`에 저장하고 `/timetable/`로 이동합니다.
6. `/timetable/`에서 수업 블록을 수정한 뒤 `/api/recommendations`를 호출합니다.
7. 추천 결과를 `sessionStorage`에 저장하고 `/recommendations/`로 이동합니다.
8. `/recommendations/`에서 추천 목록을 검색/필터하고 프로그램 상세 정보를 확인합니다.

## 브라우저 저장 키

| 키 | 저장 내용 |
| --- | --- |
| `hsportal:timetable` | 추출/수정된 시간표 JSON |
| `hsportal:source-file` | 업로드 파일명, 크기, 타입, 분석 시각, 크롭 좌표 |
| `hsportal:recommendations` | 추천 API 응답 |

모든 값은 `sessionStorage`에 저장되므로 브라우저 탭을 닫으면 사라집니다.

## 메인 화면

`public/app.js`는 다음 API를 호출합니다.

- `GET /api/heartbeat`: 환경과 모델명 표시, dev 환경이면 JSON 직접 입력 버튼 표시
- `GET /api/hsportal/crawl-status`: 비교과 데이터 준비 상태 표시
- `POST /api/timetable/extract`: 시간표 이미지 분석

이미지 업로드는 파일 선택과 드래그 앤 드롭을 모두 지원합니다. 크롭이 적용되면 원본 파일 정보와 크롭 좌표가 함께 저장됩니다.

## 시간표 편집 화면

`timetable/app.js`는 시간표를 08:00부터 22:00까지 30분 단위 그리드로 표시합니다.

- 빈 시간대를 드래그하면 새 수업을 추가합니다.
- 수업 블록을 드래그하면 요일과 시간이 바뀝니다.
- 수업 블록을 클릭하면 수업명, 요일, 시작/종료 시간을 편집합니다.
- 같은 요일의 수업 시간이 겹치면 저장 또는 추천 진행을 막습니다.
- 최종 JSON을 확인하고 클립보드로 복사할 수 있습니다.

추천 요청은 `include_needs_review=true`, `include_unavailable=true`, `limit=100`으로 호출해 결과 화면에서 전체 상태를 필터링할 수 있게 합니다.

## 추천 결과 화면

`recommendations/app.js`는 추천 API 응답을 읽어 목록과 상세 모달을 렌더링합니다.

- 상태별 개수 요약: 가능, 확인 필요, 불가
- 검색 대상: 제목, 대분류, 세부분류, 운영 부서
- 필터: 전체, 참여 가능, 확인 필요, 참여 불가
- 상세 모달: 추천 점수, 이유, 포인트, 신청 기간, 신청 현황, 운영 부서, 일정, 경고, 충돌 수업, 포털 링크

## 개발용 테스트 화면

`/test/`는 운영 흐름과 별도로 API를 직접 확인하기 위한 화면입니다.

- 이미지 업로드 후 시간표 JSON 확인
- 샘플 시간표 JSON 입력
- 추천 API 호출 결과를 카드 형태로 확인

이 화면은 유지보수와 수동 QA 용도이며, 사용자의 기본 흐름은 `/`, `/timetable/`, `/recommendations/`입니다.

## 실행 방식

프론트엔드는 별도 dev server를 사용하지 않습니다. 루트에서 FastAPI 서버를 실행하면 같은 주소에서 정적 파일과 API를 함께 사용할 수 있습니다.

```bash
python -m uvicorn main:app --reload
```
