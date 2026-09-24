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
from src.prompts.case_summarization import SUMMARIZATION_SYSTEM_PROMPT
from src.services.llm_service import xllm_service
from src.utils.helper import build_content_parts


async def generate_summary(case_text: str | None = None, urls: list | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        content_parts = await build_content_parts(client, case_text, urls)

    messages: LanguageModelInput = [
        ("system", SUMMARIZATION_SYSTEM_PROMPT),
        ("user", content_parts),
    ]

    model = xllm_service.get_summarization_model().bind(response_format={"type": "json_object"})
    try:
        response = await model.ainvoke(messages)
    except openai.RateLimitError as e:
        raise TooManyRequestsAPIException() from e
    except openai.BadRequestError as e:
        raise BadRequestAPIException(str(e)) from e
    except openai.APITimeoutError as e:
        raise GatewayTimeoutAPIException() from e
    except openai.APIConnectionError as e:
        raise ServiceUnavailableAPIException("Could not reach the summarization model") from e

    if not isinstance(response.content, str):
        raise BadRequestAPIException("Summarization model returned an unexpected response format")
    return json.loads(response.content)
