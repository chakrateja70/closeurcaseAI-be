import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

URL = "https://example.com/files/affidavit.pdf"


def _mock_model(content: str, finish_reason: str = "stop"):
    model = MagicMock()
    model.bind.return_value = model
    model.ainvoke = AsyncMock()
    model.ainvoke.return_value.content = content
    model.ainvoke.return_value.response_metadata = {"finish_reason": finish_reason}
    return model


def test_generate_counter_requires_url():
    response = client.post("/counter-generation/generate-counter", json={})
    assert response.status_code == 422


def test_generate_counter_rejects_text_input():
    response = client.post("/counter-generation/generate-counter", json={"case_text": "some text"})
    assert response.status_code == 422


@patch("src.services.counter_generation.build_content_parts", new_callable=AsyncMock)
@patch("src.services.counter_generation.xllm_service")
def test_generate_counter_sends_whole_document_to_llm(mock_llm_service, mock_parts):
    mock_parts.return_value = [{"type": "file", "file": {}}]
    item = {"paragraph_number": "1", "argument": "a", "counter_argument": "c"}
    model = _mock_model(json.dumps({"counter_arguments": [item]}))
    mock_llm_service.get_counter_generation_model.return_value = model

    response = client.post("/counter-generation/generate-counter", json={"url": URL})

    assert response.status_code == 200
    assert response.json()["data"]["counter_arguments"][0]["paragraph_number"] == "1"
    assert mock_parts.call_args.args[1:] == (None, [URL])
    model.ainvoke.assert_awaited_once()


@patch("src.services.counter_generation.build_content_parts", new_callable=AsyncMock)
@patch("src.services.counter_generation.xllm_service")
def test_generate_counter_truncated_output_returns_400(mock_llm_service, mock_parts):
    mock_parts.return_value = []
    mock_llm_service.get_counter_generation_model.return_value = _mock_model("{}", "length")

    response = client.post("/counter-generation/generate-counter", json={"url": URL})

    assert response.status_code == 400
