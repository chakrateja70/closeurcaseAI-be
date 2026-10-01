import asyncio

import httpx
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable

from src.core.exceptions import BadRequestAPIException, openai_errors, parse_json_content
from src.prompts.counter_generation import (
    COUNTER_GENERATION_SYSTEM_PROMPT,
    OUTLINE_TASK,
    PARAGRAPH_TASK,
)
from src.services.llm_service import xllm_service
from src.utils.helper import build_content_parts

# ponytail: fixed cap on concurrent paragraph calls; tune if OpenAI rate limits (429) appear.
MAX_PARALLEL_PARAGRAPHS = 40


async def ask(model: Runnable, content_parts: list, task: str) -> dict:
    """One call with the shared prefix (system prompt + affidavit) and a task at the end, so
    every call after the first reads the affidavit from OpenAI's prompt cache."""
    messages: LanguageModelInput = [
        ("system", COUNTER_GENERATION_SYSTEM_PROMPT),
        ("user", [*content_parts, {"type": "text", "text": task}]),
    ]
    with openai_errors("counter"):
        response = await model.ainvoke(messages)

    # Responses API: truncation shows as status "incomplete"; content is a list of blocks
    # (reasoning + text), so read the joined text.
    if response.response_metadata.get("status") == "incomplete":
        raise BadRequestAPIException("Affidavit too long to counter completely")
    return parse_json_content(response.text, "counter")


async def generate_counter(url: str) -> dict:
    """Outline the affidavit (law regime + paragraph numbers), then counter every paragraph in
    parallel; wall time is roughly the outline plus the slowest single paragraph."""
    async with httpx.AsyncClient(timeout=240) as client:
        content_parts = await build_content_parts(client, None, [url])

    model = xllm_service.get_counter_generation_model().bind(
        response_format={"type": "json_object"}
    )
    outline = await ask(model, content_parts, OUTLINE_TASK)
    regime = outline.get("applicable_law_regime")
    paragraph_numbers = [str(n) for n in outline.get("paragraph_numbers") or []]
    if not paragraph_numbers:
        # The model explains why in applicable_law_regime (e.g. unreadable scan).
        raise BadRequestAPIException(regime or "No paragraphs could be read from the affidavit")

    limit = asyncio.Semaphore(MAX_PARALLEL_PARAGRAPHS)

    async def counter_paragraph(number: str) -> dict:
        task = f"{PARAGRAPH_TASK}\nParagraph: {number}\nApplicable law regime: {regime}"
        async with limit:
            counter = await ask(model, content_parts, task)
        counter["paragraph_number"] = number  # keep the outline's numbering consistent
        return counter

    counters = await asyncio.gather(*(counter_paragraph(n) for n in paragraph_numbers))
    return {"applicable_law_regime": regime, "counter_arguments": counters}
