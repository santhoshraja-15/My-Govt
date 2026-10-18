"""LLM client abstraction. No provider is required: with LLM_PROVIDER=none the assistant answers
extractively from its sources. API keys come from settings/environment only."""
from __future__ import annotations

from typing import Optional, Protocol

from app.core.config import settings


class LLMClient(Protocol):
    async def generate(self, system: str, prompt: str) -> str: ...


class OpenAIClient:
    async def generate(self, system: str, prompt: str) -> str:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL, max_tokens=settings.LLM_MAX_TOKENS, temperature=settings.LLM_TEMPERATURE,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


class GoogleClient:
    async def generate(self, system: str, prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=settings.LLM_API_KEY)
        model = genai.GenerativeModel(settings.LLM_MODEL)
        resp = await model.generate_content_async(f"{system}\n\n{prompt}")
        return resp.text or ""


def get_llm() -> Optional[LLMClient]:
    """The configured client, or None when no provider/key is configured."""
    if settings.LLM_PROVIDER == "none" or not settings.LLM_API_KEY:
        return None
    if settings.LLM_PROVIDER == "openai":
        return OpenAIClient()
    if settings.LLM_PROVIDER == "google":
        return GoogleClient()
    raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")
