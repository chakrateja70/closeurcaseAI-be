import json

import httpx
import openai
from langchain_core.language_models import LanguageModelInput

from src.core.exceptions import (
    BadRequestAPIException,
    GatewayTimeoutAPIException,
    ServiceUnavailableAPIException,
    TooManyRequestsAPIException,
)
from src.prompts.counter_generation import COUNTER_GENERATION_SYSTEM_PROMPT
from src.services.llm_service import xllm_service
from src.utils.helper import build_content_parts


async def generate_counter(url: str) -> dict:
    """Send the whole affidavit (document/image URL) to the LLM in a single call."""
    async with httpx.AsyncClient(timeout=90) as client:
        content_parts = await build_content_parts(client, None, [url])

    messages: LanguageModelInput = [
        ("system", COUNTER_GENERATION_SYSTEM_PROMPT),
        ("user", content_parts),
    ]

    model = xllm_service.get_counter_generation_model().bind(
        response_format={"type": "json_object"}
    )
    try:
        response = await model.ainvoke(messages)
    except openai.RateLimitError as e:
        raise TooManyRequestsAPIException() from e
    except openai.BadRequestError as e:
        raise BadRequestAPIException(str(e)) from e
    except openai.APITimeoutError as e:
        raise GatewayTimeoutAPIException() from e
    except openai.APIConnectionError as e:
        raise ServiceUnavailableAPIException("Could not reach the counter model") from e

    if not isinstance(response.content, str):
        raise BadRequestAPIException("Counter model returned an unexpected response format")
    if response.response_metadata.get("finish_reason") == "length":
        raise BadRequestAPIException("Affidavit too long to counter completely")
    return json.loads(response.content)
