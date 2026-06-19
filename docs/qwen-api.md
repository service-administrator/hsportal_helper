# Qwen VLM API 설정

이 프로젝트는 시간표 이미지에서 수업 정보를 추출하기 위해 Vision Language Model API를 사용합니다. 사용한 모델은 Alibaba Cloud Model Studio의 `qwen3-vl-plus`이며, 대체 모델로 Hugging Face Inference Providers의 `Qwen/Qwen3-VL-30B-A3B-Instruct`를 검토했습니다.

요금 정보는 2026년 6월 19일 확인 기준입니다. 모델 요금과 무료 크레딧 정책은 서비스 제공자에 의해 변경될 수 있으므로, 실제 배포 전에는 공식 페이지를 다시 확인해야 합니다.

## Alibaba Cloud Model Studio

- 사용 모델: `qwen3-vl-plus`
- 문서: [Alibaba Cloud Model Studio OpenAI-compatible Vision](https://www.alibabacloud.com/help/en/model-studio/qwen-vl-compatible-with-openai)
- 모델/요금 문서: [Alibaba Cloud Model Studio Models](https://www.alibabacloud.com/help/en/model-studio/models)
- 사용 endpoint: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

Alibaba Cloud 문서에 따르면 Qwen-VL 모델은 OpenAI-compatible 형식을 지원합니다. 기존 OpenAI Vision 앱에서 `base_url`, `api_key`, `model`을 바꾸는 방식으로 이전할 수 있습니다.

### 모델 특성

| 항목 | 내용 |
| --- | --- |
| 모델명 | `qwen3-vl-plus` |
| 현재 stable 버전 | `qwen3-vl-plus-2025-12-19` |
| 입력 | 텍스트 + 이미지 |
| 출력 | 텍스트 |
| context window | 262,144 tokens |
| 최대 입력 | Thinking 258,048 tokens / Non-thinking 260,096 tokens |
| 이미지당 최대 토큰 | 16,384 tokens |
| 최대 출력 | 32,768 tokens |
| 최대 CoT | 81,920 tokens |

### 요금

International / Hong Kong / EU 문서 기준 `qwen3-vl-plus`는 요청별 입력 토큰 수에 따라 tiered billing이 적용됩니다. Thinking mode와 non-thinking mode의 입력/출력 단가는 동일합니다.

| 입력 토큰 수 | 입력 요금 | 출력 요금 |
| --- | ---: | ---: |
| 0 < tokens <= 32K | $0.20 / 1M tokens | $1.60 / 1M tokens |
| 32K < tokens <= 128K | $0.30 / 1M tokens | $2.40 / 1M tokens |
| 128K < tokens <= 256K | $0.60 / 1M tokens | $4.80 / 1M tokens |

이미지 입력은 이미지 토큰으로 변환되어 입력 토큰에 포함됩니다. Thinking mode에서 reasoning 과정이 출력되는 경우, 해당 토큰도 출력 토큰 비용에 포함됩니다.

## Hugging Face Inference Providers

- 사용 모델: `Qwen/Qwen3-VL-30B-A3B-Instruct`
- 모델 페이지: [Qwen/Qwen3-VL-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct)
- 요금 페이지: [Hugging Face Inference Providers](https://huggingface.co/inference/models?model=Qwen/Qwen3-VL-30B-A3B-Instruct)
- Billing 문서: [Pricing and Billing](https://huggingface.co/docs/inference-providers/en/pricing)

Hugging Face 모델 페이지 기준 `Qwen/Qwen3-VL-30B-A3B-Instruct`는 image-text-to-text 모델이며, Apache 2.0 라이선스로 공개되어 있습니다. 모델 크기는 약 31B parameters이고 BF16 tensor를 사용합니다.

### 모델 특성

| 항목 | 내용 |
| --- | --- |
| 모델명 | `Qwen/Qwen3-VL-30B-A3B-Instruct` |
| provider | Novita |
| 입력 | 텍스트 + 이미지 |
| 출력 | 텍스트 |
| context | 131,072 tokens |
| tools | 지원 |
| structured output | 지원 |

### 요금

Hugging Face Inference Providers의 해당 모델 페이지 기준 Novita provider 요금은 다음과 같습니다.

| Provider | 입력 요금 | 출력 요금 | Context |
| --- | ---: | ---: | ---: |
| Novita | $0.20 / 1M tokens | $0.70 / 1M tokens | 131,072 tokens |

Hugging Face Inference Providers는 월별 크레딧을 제공합니다. 문서 기준 Free user는 $0.10, PRO user는 $2.00, Team 또는 Enterprise 조직은 좌석당 $2.00의 월별 크레딧이 제공됩니다. Hugging Face 라우팅을 사용하면 이 크레딧이 먼저 적용되며, 추가 사용량은 pay-as-you-go 방식으로 청구됩니다.

## API 사용 방식

1. 사용자가 시간표 이미지를 업로드합니다.
2. 서버가 이미지를 검증하고 WebP로 정규화합니다.
3. 이미지를 data URL로 변환합니다.
4. `llm.tasks.timetable`에서 JSON 출력 instruction과 이미지를 묶어 VLM task를 만듭니다.
5. `LLMService`가 OpenAI-compatible Chat Completions API를 호출합니다.
6. 응답 텍스트에서 JSON을 파싱하고 `TimetableExtractionResult` 스키마로 검증합니다.
