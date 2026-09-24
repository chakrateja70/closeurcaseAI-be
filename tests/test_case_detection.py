import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _mock_model(payload: dict):
    bound = AsyncMock()
    bound.ainvoke.return_value.content = json.dumps(payload)
    mock = AsyncMock()
    mock.bind = lambda **_: bound
    return mock


@patch("src.services.case_detection.xllm_service")
def test_detect_case_returns_matched_category(mock_llm_service):
    mock_llm_service.get_detection_model.return_value = _mock_model(
        {"categoryId": "cat_9", "subCategoryId": "spec_9_1"}
    )

    response = client.post(
        "/detection/detect-case",
        json={"query": "My landlord is refusing to return my security deposit."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["categoryId"] == "cat_9"
    assert body["data"]["categoryName"] == "Property Law"
    assert body["data"]["subCategoryId"] == "spec_9_1"
    assert body["data"]["subCategoryName"] == "Landlord/Tenant"


@patch("src.services.case_detection.xllm_service")
def test_detect_case_no_match_returns_nulls(mock_llm_service):
    mock_llm_service.get_detection_model.return_value = _mock_model(
        {"categoryId": None, "subCategoryId": None}
    )

    response = client.post("/detection/detect-case", json={"query": "What's the weather today?"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["categoryId"] is None
    assert body["data"]["subCategoryId"] is None


@patch("src.services.case_detection.xllm_service")
def test_detect_case_unknown_id_returns_400(mock_llm_service):
    mock_llm_service.get_detection_model.return_value = _mock_model(
        {"categoryId": "cat_999", "subCategoryId": None}
    )

    response = client.post("/detection/detect-case", json={"query": "some legal issue"})

    assert response.status_code == 400
