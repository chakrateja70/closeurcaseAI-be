import json
from pathlib import Path

import openai

from src.core.exceptions import (
    BadRequestAPIException,
    GatewayTimeoutAPIException,
    ServiceUnavailableAPIException,
    TooManyRequestsAPIException,
)
from src.prompts.case_detection import build_detection_system_prompt
from src.services.llm_service import xllm_service

MASTER_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "master_data" / "case_detection.json"
)
CATEGORIES = json.loads(MASTER_DATA_PATH.read_text(encoding="utf-8"))["data"]
DETECTION_SYSTEM_PROMPT = build_detection_system_prompt(json.dumps(CATEGORIES))

# Lookups for validating/resolving the LLM's chosen ids.
CATEGORY_BY_ID = {cat["id"]: cat for cat in CATEGORIES}
SUBCATEGORY_BY_ID = {sub["id"]: sub for cat in CATEGORIES for sub in cat["subCategories"]}


async def detect_case(user_input: str) -> dict:
    """Detect the category and subcategory of a legal query using LLM."""
    messages = [
        ("system", DETECTION_SYSTEM_PROMPT),
        ("user", user_input),
    ]

    model = xllm_service.get_detection_model().bind(response_format={"type": "json_object"})
    try:
        response = await model.ainvoke(messages)
    except openai.RateLimitError as e:
        raise TooManyRequestsAPIException() from e
    except openai.BadRequestError as e:
        raise BadRequestAPIException(str(e)) from e
    except openai.APITimeoutError as e:
        raise GatewayTimeoutAPIException() from e
    except openai.APIConnectionError as e:
        raise ServiceUnavailableAPIException("Could not reach the detection model") from e

    if not isinstance(response.content, str):
        raise BadRequestAPIException("Detection model returned an unexpected response format")
    result = json.loads(response.content)
    category_id = result.get("categoryId")
    subcategory_id = result.get("subCategoryId")

    category = CATEGORY_BY_ID.get(category_id)
    subcategory = SUBCATEGORY_BY_ID.get(subcategory_id)
    if subcategory and subcategory["categoryId"] != category_id:
        subcategory = None
    if category_id and not category:
        raise BadRequestAPIException(f"Model returned unknown categoryId: {category_id}")
    if subcategory_id and not subcategory:
        raise BadRequestAPIException(f"Model returned unknown subCategoryId: {subcategory_id}")

    return {
        "categoryId": category["id"] if category else None,
        "categoryName": category["name"] if category else None,
        "subCategoryId": subcategory["id"] if subcategory else None,
        "subCategoryName": subcategory["name"] if subcategory else None,
    }
