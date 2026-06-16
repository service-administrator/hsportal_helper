import base64
from dataclasses import dataclass

from llm.config import get_llm_settings
from llm.exceptions import ImagePayloadError
from util.image_processing import (
    SUPPORTED_INPUT_FORMATS,
    inspect_image,
    normalize_image_for_vlm,
)


@dataclass(frozen=True)
class ImagePayload:
    data_url: str
    mime_type: str
    size_bytes: int
    width: int
    height: int


def prepare_image_data_url(
    image_bytes: bytes,
    *,
    content_type: str | None = None,
    max_bytes: int | None = None,
) -> ImagePayload:
    """Validate image bytes and return a base64 data URL for a vision request."""
    if not image_bytes:
        raise ImagePayloadError("Image payload is empty.")

    byte_limit = max_bytes if max_bytes is not None else get_llm_settings().llm_max_image_bytes
    if len(image_bytes) > byte_limit:
        raise ImagePayloadError(
            f"Image payload is too large: {len(image_bytes)} bytes exceeds {byte_limit} bytes."
        )

    try:
        inspection = inspect_image(image_bytes)
    except ValueError as exc:
        raise ImagePayloadError(str(exc)) from exc

    if content_type and content_type != "application/octet-stream":
        normalized_content_type = content_type.split(";")[0].strip().lower()
        if normalized_content_type not in SUPPORTED_INPUT_FORMATS.values():
            raise ImagePayloadError(f"Unsupported image content type: {content_type}")
        if normalized_content_type != inspection.mime_type:
            raise ImagePayloadError(
                f"Image content type mismatch: got {content_type}, detected {inspection.mime_type}."
            )

    try:
        normalized_image = normalize_image_for_vlm(image_bytes)
    except ValueError as exc:
        raise ImagePayloadError(str(exc)) from exc

    encoded = base64.b64encode(normalized_image.bytes).decode("ascii")
    return ImagePayload(
        data_url=f"data:{normalized_image.mime_type};base64,{encoded}",
        mime_type=normalized_image.mime_type,
        size_bytes=len(normalized_image.bytes),
        width=normalized_image.width,
        height=normalized_image.height,
    )
