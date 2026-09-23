import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
import openai

from src.core.exceptions import (
    BadRequestAPIException,
    GatewayTimeoutAPIException,
    ServiceUnavailableAPIException,
    TooManyRequestsAPIException,
)
from src.prompts.case_summarization import SUMMARIZATION_SYSTEM_PROMPT
from src.services.llm_service import xllm_service
from src.utils.helper import build_file_part, build_image_part

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}


async def generate_summary(case_text: str | None = None, urls: list | None = None) -> dict:
    content_parts = []

    if case_text:
        content_parts.append({"type": "text", "text": f"Case Text:\n{case_text}"})

    async with httpx.AsyncClient(timeout=10) as client:
        for url in urls or []:
            url = str(url)
            ext = Path(urlparse(url).path).suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                content_parts.append(await build_image_part(client, url))
            elif ext in DOCUMENT_EXTENSIONS:
                content_parts.append(await build_file_part(client, url))
            else:
                raise BadRequestAPIException(
                    f"Unsupported file type '{ext or 'unknown'}' for URL: {url}. "
                    f"Supported extensions: {sorted(IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS)}"
                )

    messages = [
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

    return json.loads(response.content)
