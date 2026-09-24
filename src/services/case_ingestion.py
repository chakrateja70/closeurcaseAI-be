import asyncio
from pathlib import Path
from urllib.parse import urlparse

import httpx
import openai
from langchain_core.language_models import LanguageModelInput

from src.core.exceptions import (
    BadRequestAPIException,
    GatewayTimeoutAPIException,
    ServiceUnavailableAPIException,
    TooManyRequestsAPIException,
)
from src.prompts.case_ingestion import EXTRACT_SYSTEM_PROMPT
from src.services.llm_service import xllm_service
from src.utils.helper import build_content_parts


async def _extract_from_url(client: httpx.AsyncClient, url: str) -> str:
    content_parts = await build_content_parts(client, case_text=None, urls=[url])
    messages: LanguageModelInput = [
        ("system", EXTRACT_SYSTEM_PROMPT),
        ("user", content_parts),
    ]

    model = xllm_service.get_case_extraction_model()
    try:
        response = await model.ainvoke(messages)
    except openai.RateLimitError as e:
        raise TooManyRequestsAPIException() from e
    except openai.BadRequestError as e:
        raise BadRequestAPIException(str(e)) from e
    except openai.APITimeoutError as e:
        raise GatewayTimeoutAPIException() from e
    except openai.APIConnectionError as e:
        raise ServiceUnavailableAPIException("Could not reach the case extraction model") from e

    if not isinstance(response.content, str):
        raise BadRequestAPIException("Case extraction model returned an unexpected response format")
    print(f"[extract_text] {url} tokens consumed: {response.usage_metadata['total_tokens']}")
    return response.content


async def extract_text(case_text: str | None = None, urls: list | None = None) -> str:
    doc_texts = []
    if urls:
        async with httpx.AsyncClient(timeout=10) as client:
            results = await asyncio.gather(*(_extract_from_url(client, str(u)) for u in urls))
        doc_texts = [
            f"{Path(urlparse(str(url)).path).name or 'document'}: {text}"
            for url, text in zip(urls, results, strict=True)
        ]

    if case_text:
        doc_texts.append(f"case_text: {case_text}")

    return "\n\n".join(doc_texts)
