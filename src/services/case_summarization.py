import httpx
from langchain_core.language_models import LanguageModelInput

from src.core.exceptions import openai_errors, parse_json_content
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
    with openai_errors("summarization"):
        response = await model.ainvoke(messages)

    return parse_json_content(response.content, "summarization")
