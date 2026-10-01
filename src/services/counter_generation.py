import httpx
from langchain_core.language_models import LanguageModelInput

from src.core.exceptions import BadRequestAPIException, openai_errors, parse_json_content
from src.prompts.counter_generation import COUNTER_GENERATION_SYSTEM_PROMPT
from src.services.llm_service import xllm_service
from src.utils.helper import build_content_parts


async def generate_counter(url: str) -> dict:
    """Send the whole affidavit (document/image URL) to the LLM in a single call."""
    async with httpx.AsyncClient(timeout=240) as client:
        content_parts = await build_content_parts(client, None, [url])

    messages: LanguageModelInput = [
        ("system", COUNTER_GENERATION_SYSTEM_PROMPT),
        ("user", content_parts),
    ]

    model = xllm_service.get_counter_generation_model().bind(
        response_format={"type": "json_object"}
    )
    with openai_errors("counter"):
        response = await model.ainvoke(messages)

    # Responses API: truncation shows as status "incomplete"; content is a list of blocks
    # (reasoning + text), so read the joined text.
    if response.response_metadata.get("status") == "incomplete":
        raise BadRequestAPIException("Affidavit too long to counter completely")
    result = parse_json_content(response.text, "counter")
    if not result.get("counter_arguments"):
        # The model explains why in applicable_law_regime (e.g. unreadable scan).
        raise BadRequestAPIException(
            result.get("applicable_law_regime") or "No paragraphs could be read from the affidavit"
        )
    return result
