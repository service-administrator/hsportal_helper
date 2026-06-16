from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

ResultT = TypeVar("ResultT", bound=BaseModel)


@dataclass(frozen=True)
class VisionImage:
    data_url: str


@dataclass(frozen=True)
class LLMJSONTask(Generic[ResultT]):
    name: str
    system_instruction: str
    prompt: str
    response_model: type[ResultT]
    images: tuple[VisionImage, ...] = ()
    temperature: float = 0.0
    max_tokens: int = 2048
    response_format: dict[str, Any] = field(default_factory=lambda: {"type": "json_object"})
    extra_body: dict[str, Any] = field(default_factory=dict)
