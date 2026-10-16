"""The one place that talks to an LLM provider."""

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

import openai
from django.conf import settings

from snippets.services.prompts import Prompt

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```[\w+-]*\n(.*?)```", re.DOTALL)


class LLMError(Exception):
    """The provider failed or returned nothing usable."""


@dataclass
class Completion:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


def extract_code(text: str) -> str:
    """Models often wrap code in a markdown fence (sometimes with prose around it); keep only the code."""
    match = _FENCE.search(text)
    return (match.group(1) if match else text).strip()


@lru_cache(maxsize=1)
def _client() -> openai.OpenAI:
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=2)


def complete(prompt: Prompt) -> Completion:
    if settings.LLM_PROVIDER == "fake":
        from snippets.services import fake_llm

        return fake_llm.complete(prompt)

    try:
        response = _client().chat.completions.create(
            model=prompt.model,
            temperature=0.2,
            messages=[{"role": "system", "content": prompt.system}, {"role": "user", "content": prompt.user}],
        )
    except openai.OpenAIError as exc:
        logger.exception("LLM call failed for task %s", prompt.task)
        raise LLMError("The model request failed. Try again in a moment.") from exc

    text = extract_code(response.choices[0].message.content or "")
    if not text:
        raise LLMError("The model returned an empty response.")
    usage = response.usage
    logger.info("LLM task=%s model=%s tokens=%s", prompt.task, prompt.model, usage and usage.total_tokens)
    return Completion(
        text=text,
        model=response.model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )
