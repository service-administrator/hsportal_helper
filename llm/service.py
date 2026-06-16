import json
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


class LLMService:
    """Internal JSON-oriented LLM runner used by backend logic."""

    def __init__(self, client: OpenAI | None = None, model: str | None = None) -> None:
        settings = get_llm_settings()
        self._client = client or get_qwen_client()
        self._model = model or settings.qwen_model
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
            raise LLMRequestError(f"LLM request failed for task '{task.name}'.") from exc

        content = response.choices[0].message.content if response.choices else None
        raw_text = _extract_message_text(content)
        payload = _parse_json_payload(raw_text, task_name=task.name)
        return _validate_payload(payload, task.response_model, task_name=task.name)


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
