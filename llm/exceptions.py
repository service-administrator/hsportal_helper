class LLMError(RuntimeError):
    """Base exception for internal LLM integration failures."""


class LLMConfigurationError(LLMError):
    """Raised when required LLM configuration is missing."""


class LLMRequestError(LLMError):
    """Raised when a model request fails before a usable response is returned."""


class LLMResponseParseError(LLMError):
    """Raised when a model response cannot be parsed as JSON."""


class LLMResponseValidationError(LLMError):
    """Raised when a parsed model response does not match the expected schema."""


class ImagePayloadError(LLMError):
    """Raised when an image cannot be prepared for a vision model request."""
