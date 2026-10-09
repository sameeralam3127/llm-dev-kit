"""A stand-in for litellm.acompletion that records calls."""

from types import SimpleNamespace
from typing import Any

import ldk_plugin_litellm.provider as provider_module


class UpstreamError(Exception):
    def __init__(self, message: str, status_code: int | None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class FakeLiteLLM:
    """Records acompletion kwargs; knows the curated models only."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_with: Exception | None = None

    async def acompletion(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.fail_with is not None:
            raise self.fail_with
        provider, _, model = kwargs["model"].partition("/")
        if model not in provider_module.DEFAULT_CLOUD_MODELS[provider]:
            raise UpstreamError(f"model {model} does not exist", 404)
        text = f"{model} says: {kwargs['messages'][-1]['content']}"
        if not kwargs.get("stream"):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

        async def chunks():
            for word in text.split(" "):
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=word))]
                )

        return chunks()
