"""Unified interface to LLM backends.

Providers:
  * mock     -- deterministic, offline; used for CI and reproducible smoke tests
  * ollama   -- local open-weight models (default: qwen2.5:3b-instruct)
  * anthropic -- Claude via the official SDK (ANTHROPIC_API_KEY), with prompt caching
  * openai   -- free-tier / openai-compatible endpoints (OPENAI_API_KEY, OPENAI_BASE_URL)
  * gemini   -- Google Gemini free tier (GEMINI_API_KEY / GOOGLE_API_KEY)
  * hf       -- Hugging Face Inference API via huggingface_hub (HF_TOKEN); CPU-friendly
  * local    -- open-weight model loaded with transformers (used on Spaces/ZeroGPU)

All providers record the exact model string used, so episodes are reproducible.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast

import requests


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


class LLMProvider(ABC):
    """Base class. Implementations return an LLMResponse for a chat completion."""

    name: str = "base"

    def __init__(self, model: str, **options):
        self.model = model
        self.options = options

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:  # pragma: no cover - interface
        raise NotImplementedError


# --------------------------------------------------------------------------------------
# Mock
# --------------------------------------------------------------------------------------


class MockProvider(LLMProvider):
    """Deterministic provider for offline tests.

    A `responder(system, messages) -> str` callable may be supplied. Without one, the
    response echoes a stable, content-derived string so runs are reproducible.
    """

    name = "mock"

    def __init__(
        self,
        model: str = "mock",
        responder: Optional[Callable[[str, list[dict[str, str]]], str]] = None,
        **options,
    ):
        super().__init__(model, **options)
        self._responder = responder

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        start = time.perf_counter()
        if self._responder is not None:
            text = self._responder(system, messages)
        else:
            last = messages[-1]["content"] if messages else ""
            text = f"[mock:{self.model}] {last[:200]}"
        return LLMResponse(
            text=text,
            model=self.model,
            completion_tokens=len(text.split()),
            latency_s=time.perf_counter() - start,
        )


# --------------------------------------------------------------------------------------
# Ollama (local)
# --------------------------------------------------------------------------------------


class OllamaProvider(LLMProvider):
    """Local open-weight models via the Ollama HTTP API."""

    name = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5:3b-instruct",
        host: Optional[str] = None,
        timeout: int = 120,
        **options,
    ):
        super().__init__(model, **options)
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        start = time.perf_counter()
        resp = requests.post(
            f"{self.host}/api/chat", json=cast(Any, payload), timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            latency_s=time.perf_counter() - start,
        )


# --------------------------------------------------------------------------------------
# Anthropic (Claude)
# --------------------------------------------------------------------------------------


class AnthropicProvider(LLMProvider):
    """Claude via the official ``anthropic`` SDK; reads ``ANTHROPIC_API_KEY``.

    Prompt caching: the system prompt is sent as a block with a ``cache_control``
    breakpoint, so the stable per-agent prefix (tools -> system) is cached across
    steps. Anthropic only caches prefixes above a model-dependent minimum length;
    shorter prompts silently run uncached, so check ``cache_read_tokens`` on the
    response. Sampling params (temperature etc.) are rejected by current models and
    are therefore not sent; ``temperature`` is accepted for interface parity only.
    """

    name = "anthropic"
    # Thinking tokens count against max_tokens on current models, so keep headroom.
    MIN_MAX_TOKENS = 4096

    def __init__(
        self,
        model: str = "claude-opus-5-5",
        effort: str = "low",
        cache_ttl: Optional[str] = None,
        client: Any = None,
        **options,
    ):
        super().__init__(model, **options)
        self.effort = effort
        self.cache_control: dict[str, str] = {"type": "ephemeral"}
        if cache_ttl:
            self.cache_control["ttl"] = cache_ttl
        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY is not set")
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError(
                    "The anthropic provider requires the 'anthropic' package. "
                    "Install the 'anthropic' extra: pip install -e '.[anthropic]'."
                ) from exc
            client = anthropic.Anthropic()
        self.client = client

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        start = time.perf_counter()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max(max_tokens, self.MIN_MAX_TOKENS),
            system=[
                {"type": "text", "text": system, "cache_control": self.cache_control}
            ],
            messages=messages,
            output_config={"effort": self.effort},
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=(usage.input_tokens or 0) + cache_read + cache_write,
            completion_tokens=usage.output_tokens or 0,
            latency_s=time.perf_counter() - start,
            cache_creation_tokens=cache_write,
            cache_read_tokens=cache_read,
        )


# --------------------------------------------------------------------------------------
# OpenAI-compatible
# --------------------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", base_url: Optional[str] = None, **options):
        super().__init__(model, **options)
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        start = time.perf_counter()
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=cast(Any, payload),
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_s=time.perf_counter() - start,
        )


# --------------------------------------------------------------------------------------
# Gemini
# --------------------------------------------------------------------------------------


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-2.0-flash", **options):
        super().__init__(model, **options)
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
            "GOOGLE_API_KEY", ""
        )
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY is not set")

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        contents = [
            {"role": "user", "parts": [{"text": m["content"]}]} for m in messages
        ]
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        start = time.perf_counter()
        resp = requests.post(url, json=cast(Any, payload), timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            text = ""
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            latency_s=time.perf_counter() - start,
        )


# --------------------------------------------------------------------------------------
# Hugging Face Inference API
# --------------------------------------------------------------------------------------


class HFInferenceProvider(LLMProvider):
    """Hugging Face Inference API (serverless). Works on CPU Spaces given HF_TOKEN."""

    name = "hf"

    def __init__(self, model: str = "Qwen/Qwen2.5-7B-Instruct", token: Optional[str] = None, **options):
        super().__init__(model, **options)
        self.token = token or os.environ.get("HF_TOKEN")
        if not self.token:
            raise RuntimeError("HF_TOKEN is not set")

        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            raise RuntimeError(
                "The Hugging Face provider requires the 'huggingface_hub' package. "
                "Install the 'space' extra or run 'pip install huggingface_hub'."
            ) from exc

        self.client = InferenceClient(model=model, token=self.token)

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        start = time.perf_counter()
        resp = self.client.chat_completion(
            messages=[{"role": "system", "content": system}, *messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_s=time.perf_counter() - start,
        )


# --------------------------------------------------------------------------------------
# Local transformers model (Space / ZeroGPU)
# --------------------------------------------------------------------------------------


class TransformersProvider(LLMProvider):
    """Local open-weight model via transformers.

    A `generator(model, system, messages, temperature, max_tokens) -> str` callable
    may be supplied so a Space can route generation through a ``spaces.GPU``-decorated
    function. Otherwise the model is loaded lazily and run on CPU/GPU directly.
    """

    name = "local"

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-0.5B-Instruct",
        generator: Optional[Callable[..., str]] = None,
        max_new_tokens: int = 256,
        **options,
    ):
        super().__init__(model, **options)
        self._generator = generator
        self.max_new_tokens = max_new_tokens
        self._pipe = None

    def _load(self):  # pragma: no cover - requires model download
        if self._pipe is None:
            from transformers import pipeline

            self._pipe = pipeline("text-generation", model=self.model)
        return self._pipe

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        start = time.perf_counter()
        if self._generator is not None:
            text = self._generator(self.model, system, messages, temperature, max_tokens)
        else:  # pragma: no cover - requires model download
            pipe = self._load()
            chat = [{"role": "system", "content": system}, *messages]
            out = pipe(
                chat,
                max_new_tokens=min(max_tokens, self.max_new_tokens),
                do_sample=temperature > 0,
                temperature=max(temperature, 1e-6),
            )
            generated = out[0]["generated_text"]
            text = generated[-1]["content"] if isinstance(generated, list) else str(generated)
        return LLMResponse(
            text=text,
            model=self.model,
            completion_tokens=len(text.split()),
            latency_s=time.perf_counter() - start,
        )


# --------------------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------------------

_REGISTRY = {
    "mock": MockProvider,
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "hf": HFInferenceProvider,
    "local": TransformersProvider,
}


def get_provider(name: str, model: Optional[str] = None, **options) -> LLMProvider:
    """Instantiate a provider by name. Falls back to mock when name is unknown."""
    key = (name or "mock").lower()
    cls = _REGISTRY.get(key, MockProvider)
    if cls is MockProvider:
        return MockProvider(model=model or "mock", **options)
    return cls(model=model, **options)  # type: ignore[call-arg]
