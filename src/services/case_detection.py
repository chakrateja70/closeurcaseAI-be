import json
from pathlib import Path

from src.core.exceptions import BadRequestAPIException, openai_errors, parse_json_content
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
# Fallback when the query matches no specific category.
OTHER_CATEGORY_ID = "cat_other"
OTHER_SUBCATEGORY_ID = "spec_other"


async def detect_case(user_input: str) -> dict:
    """Detect the category and subcategory of a legal query using LLM."""
    messages = [
        ("system", DETECTION_SYSTEM_PROMPT),
        ("user", user_input),
    ]

    model = xllm_service.get_detection_model().bind(response_format={"type": "json_object"})
    with openai_errors("detection"):
        response = await model.ainvoke(messages)

    result = parse_json_content(response.content, "detection")
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
    if not category:
        category = CATEGORY_BY_ID[OTHER_CATEGORY_ID]
        subcategory = SUBCATEGORY_BY_ID[OTHER_SUBCATEGORY_ID]

    return {
        "categoryId": category["id"],
        "categoryName": category["name"],
        "subCategoryId": subcategory["id"] if subcategory else None,
        "subCategoryName": subcategory["name"] if subcategory else None,
    }
