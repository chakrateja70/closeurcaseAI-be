import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

URL = "https://example.com/files/affidavit.pdf"
ENDPOINT = "/ai/counter-generation/generate-counter"


def _mock_model(text: str, status: str = "completed"):
    model = MagicMock()
    model.bind.return_value = model
    model.ainvoke = AsyncMock()
    model.ainvoke.return_value.text = text
    model.ainvoke.return_value.response_metadata = {"status": status}
    return model


def test_generate_counter_requires_url():
    response = client.post(ENDPOINT, json={})
    assert response.status_code == 422


def test_generate_counter_rejects_text_input():
    response = client.post(ENDPOINT, json={"case_text": "some text"})
    assert response.status_code == 422


@patch("src.services.counter_generation.build_content_parts", new_callable=AsyncMock)
@patch("src.services.counter_generation.xllm_service")
def test_generate_counter_sends_whole_document_to_llm(mock_llm_service, mock_parts):
    mock_parts.return_value = [{"type": "file", "file": {}}]
    basis = {
        "act": "Indian Evidence Act, 1872",
        "provision": "Section 101",
        "corresponding_provision": "Section 104 BSA",
        "application": "Claimant must prove the allegation",
    }
    item = {
        "paragraph_number": "1",
        "argument": "a",
        "counter_argument": "c",
        "legal_basis": [basis],
    }
    llm_output = {"applicable_law_regime": "IPC/CrPC/IEA", "counter_arguments": [item]}
    model = _mock_model(json.dumps(llm_output))
    mock_llm_service.get_counter_generation_model.return_value = model

    response = client.post(ENDPOINT, json={"url": URL})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["applicable_law_regime"] == "IPC/CrPC/IEA"
    counter = data["counter_arguments"][0]
    assert counter["paragraph_number"] == "1"
    assert counter["legal_basis"][0]["provision"] == "Section 101"
    assert counter["legal_basis"][0]["needs_verification"] is False
    assert counter["case_references"] == []
    assert "principle" not in counter["legal_basis"][0]
    assert "cross_references" not in counter
    assert mock_parts.call_args.args[1:] == (None, [URL])
    model.ainvoke.assert_awaited_once()


@patch("src.services.counter_generation.build_content_parts", new_callable=AsyncMock)
@patch("src.services.counter_generation.xllm_service")
def test_generate_counter_truncated_output_returns_400(mock_llm_service, mock_parts):
    mock_parts.return_value = []
    mock_llm_service.get_counter_generation_model.return_value = _mock_model("{}", "incomplete")

    response = client.post(ENDPOINT, json={"url": URL})

    assert response.status_code == 400


@patch("src.services.counter_generation.build_content_parts", new_callable=AsyncMock)
@patch("src.services.counter_generation.xllm_service")
def test_generate_counter_empty_counters_returns_400(mock_llm_service, mock_parts):
    mock_parts.return_value = []
    llm_output = {"applicable_law_regime": "Unreadable scan", "counter_arguments": []}
    mock_llm_service.get_counter_generation_model.return_value = _mock_model(json.dumps(llm_output))

    response = client.post(ENDPOINT, json={"url": URL})

    assert response.status_code == 400
    assert response.json()["detail"]["error_message"] == "Unreadable scan"
