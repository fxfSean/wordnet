from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .config import LLMSettings


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    model: str | None = None


class ProviderError(Exception):
    def __init__(self, code: str, *, retryable: bool = False, retry_after: float = 0):
        super().__init__(code)
        self.retryable = retryable
        self.retry_after = retry_after


class ChatProvider:
    def __init__(self, settings: LLMSettings, *, transport=None):
        self.settings = settings
        self.client = httpx.Client(
            timeout=settings.request_timeout,
            transport=transport,
            follow_redirects=False,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.client.close()

    def complete(self, messages: list[dict]) -> Completion:
        settings = self.settings
        body = {
            "model": settings.model,
            "messages": messages,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        host = urlsplit(settings.base_url).hostname
        if settings.provider == "deepseek":
            body["response_format"] = {"type": "json_object"}
            if host == "api.deepseek.com":
                body["thinking"] = {"type": "disabled"}
        elif settings.json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            result = self.client.post(
                settings.base_url.rstrip("/") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.api_key.get_secret_value()}"
                },
                json=body,
            )
        except httpx.TimeoutException as error:
            raise ProviderError("timeout", retryable=True) from error
        except httpx.RequestError as error:
            raise ProviderError("network_error", retryable=True) from error
        if not result.is_success:
            status = result.status_code
            try:
                retry_after = min(
                    60.0, max(0.0, float(result.headers.get("Retry-After", "0")))
                )
            except ValueError:
                retry_after = 0
            raise ProviderError(
                f"http_{status}",
                retryable=status == 429 or 500 <= status <= 599,
                retry_after=retry_after,
            )
        try:
            payload = result.json()
            usage = payload.get("usage") or {}
            text = payload["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise TypeError
        except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
            raise ProviderError("invalid_provider_response", retryable=True) from error
        return Completion(
            text,
            token(usage, "prompt_tokens"),
            token(usage, "completion_tokens"),
            payload.get("model"),
        )


def token(usage: object, field: str) -> int | None:
    value = usage.get(field) if isinstance(usage, dict) else None
    return value if type(value) is int and value >= 0 else None
