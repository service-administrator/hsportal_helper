import json
import logging
import re
from typing import Any, cast

from openai import APIError, OpenAI
from pydantic import BaseModel, ValidationError

from llm.config import get_llm_settings
from llm.exceptions import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseParseError,
    LLMResponseValidationError,
)
from llm.qwen_client import get_qwen_client
from llm.tasks.base import LLMJSONTask, ResultT

logger = logging.getLogger(__name__)
LOG_PREVIEW_LIMIT = 1000


class LLMService:
    """Internal JSON-oriented LLM runner used by backend logic."""

    def __init__(self, client: OpenAI | None = None, model: str | None = None) -> None:
        settings = get_llm_settings()
        self._client = client or get_qwen_client()
        self._model = model or settings.qwen_model
        self._log_api_response = settings.app_env.strip().lower() == "dev"
        if not self._model:
            raise LLMConfigurationError("QWEN_MODEL is not configured.")

    def run_json_task(self, task: LLMJSONTask[ResultT]) -> ResultT:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=_build_messages(task),
                temperature=task.temperature,
                max_tokens=task.max_tokens,
                response_format=task.response_format,
                extra_body=task.extra_body,
            )
        except APIError as exc:
            error_detail = _api_error_detail(exc)
            logger.exception(
                "LLM API request failed. task=%s model=%s %s body=%s",
                task.name,
                self._model,
                error_detail,
                _preview(getattr(exc, "body", None)),
            )
            raise LLMRequestError(
                f"LLM API request failed for task '{task.name}': {error_detail}"
            ) from exc
        if self._log_api_response:
            logger.info(
                "LLM API response. task=%s model=%s response=%s",
                task.name,
                self._model,
                _serialize_response(response),
            )

        content = response.choices[0].message.content if response.choices else None
        try:
            raw_text = _extract_message_text(content)
        except LLMResponseParseError:
            logger.exception(
                "LLM response did not contain usable text. "
                "task=%s model=%s choices_count=%s content_type=%s",
                task.name,
                self._model,
                len(response.choices) if response.choices else 0,
                type(content).__name__,
            )
            raise

        try:
            payload = _parse_json_payload(raw_text, task_name=task.name)
        except LLMResponseParseError:
            logger.exception(
                "LLM response JSON parsing failed. task=%s model=%s raw_response_preview=%s",
                task.name,
                self._model,
                _preview(raw_text),
            )
            raise

        try:
            return _validate_payload(payload, task.response_model, task_name=task.name)
        except LLMResponseValidationError:
            logger.exception(
                "LLM response schema validation failed. task=%s model=%s payload_preview=%s",
                task.name,
                self._model,
                _preview(payload),
            )
            raise


def _build_messages(task: LLMJSONTask[BaseModel]) -> list[dict[str, Any]]:
    user_content: list[dict[str, Any]] = [{"type": "text", "text": task.prompt}]
    user_content.extend(
        {"type": "image_url", "image_url": {"url": image.data_url}} for image in task.images
    )
    return [
        {"role": "system", "content": task.system_instruction},
        {"role": "user", "content": user_content},
    ]


def _extract_message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        return "\n".join(text_parts)
    raise LLMResponseParseError("LLM response did not contain text content.")


def _parse_json_payload(raw_text: str, *, task_name: str) -> Any:
    text = _strip_markdown_code_fence(raw_text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not object_match:
            raise LLMResponseParseError(
                f"LLM response for task '{task_name}' did not contain a JSON object."
            ) from exc
        try:
            return json.loads(object_match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(
                f"LLM response for task '{task_name}' was not valid JSON."
            ) from exc


def _strip_markdown_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _validate_payload(payload: Any, response_model: type[ResultT], *, task_name: str) -> ResultT:
    try:
        return cast(ResultT, response_model.model_validate(payload))
    except ValidationError as exc:
        raise LLMResponseValidationError(
            f"LLM response for task '{task_name}' did not match the expected schema."
        ) from exc


def _preview(value: Any) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)

    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= LOG_PREVIEW_LIMIT:
        return text
    return f"{text[:LOG_PREVIEW_LIMIT]}...(truncated)"


def _serialize_response(response: Any) -> str:
    if hasattr(response, "model_dump_json"):
        try:
            return response.model_dump_json(indent=2)
        except TypeError:
            return response.model_dump_json()
        except Exception:
            pass

    if hasattr(response, "model_dump"):
        try:
            value = response.model_dump(mode="json")
        except TypeError:
            value = response.model_dump()
        except Exception:
            value = _to_jsonable(response)
    else:
        value = _to_jsonable(response)

    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: _to_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def _api_error_detail(exc: APIError) -> str:
    body = getattr(exc, "body", None)
    message = getattr(exc, "message", None) or str(exc)
    code = None
    request_id = getattr(exc, "request_id", None)

    if isinstance(body, dict):
        error_body = body.get("error")
        if isinstance(error_body, dict):
            message = str(error_body.get("message") or message)
            code = error_body.get("code") or error_body.get("type")
            request_id = request_id or error_body.get("id")
        else:
            message = str(body.get("message") or message)
            code = body.get("code") or body.get("type")
            request_id = request_id or body.get("id")

    parts = [f"status_code={getattr(exc, 'status_code', None)}"]
    if code:
        parts.append(f"code={code}")
    if request_id:
        parts.append(f"request_id={request_id}")
    if message:
        parts.append(f"message={message}")
    return " ".join(parts)
