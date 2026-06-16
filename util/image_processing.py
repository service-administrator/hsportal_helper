from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

NORMALIZED_IMAGE_MAX_EDGE = 2000
NORMALIZED_IMAGE_FORMAT = "WEBP"
NORMALIZED_IMAGE_MIME_TYPE = "image/webp"
WEBP_QUALITY = 92

SUPPORTED_INPUT_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class NormalizedImage:
    bytes: bytes
    mime_type: str
    width: int
    height: int


@dataclass(frozen=True)
class ImageInspection:
    format: str
    mime_type: str
    width: int
    height: int


def inspect_image(image_bytes: bytes) -> ImageInspection:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise ValueError("Unsupported or invalid image file.") from exc

    if image_format not in SUPPORTED_INPUT_FORMATS:
        raise ValueError(f"Unsupported image format: {image_format}")

    return ImageInspection(
        format=image_format,
        mime_type=SUPPORTED_INPUT_FORMATS[image_format],
        width=width,
        height=height,
    )


def normalize_image_for_vlm(
    image_bytes: bytes,
    *,
    max_edge: int = NORMALIZED_IMAGE_MAX_EDGE,
) -> NormalizedImage:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image = _flatten_to_rgb(image)
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

            output = BytesIO()
            image.save(
                output,
                format=NORMALIZED_IMAGE_FORMAT,
                quality=WEBP_QUALITY,
                method=6,
            )
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise ValueError("Unsupported or invalid image file.") from exc

    return NormalizedImage(
        bytes=output.getvalue(),
        mime_type=NORMALIZED_IMAGE_MIME_TYPE,
        width=image.width,
        height=image.height,
    )


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba_image = image.convert("RGBA")
        background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
        background.alpha_composite(rgba_image)
        return background.convert("RGB")

    if image.mode != "RGB":
        return image.convert("RGB")

    return image.copy()
