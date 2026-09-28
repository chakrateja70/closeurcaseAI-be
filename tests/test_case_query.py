import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

CHUNKS = [{"id": "c1-0", "text": "Petitioner is S/o. X", "document_name": "petition.pdf"}]


def _mock_model(payload: dict):
    bound = AsyncMock()
    bound.ainvoke.return_value.content = json.dumps(payload)
    model = MagicMock()
    model.bind = lambda **_: bound
    return model


@patch("src.services.case_ingestion.search_chunks", new_callable=AsyncMock)
@patch("src.services.case_ingestion.xllm_service")
def test_query_keeps_only_retrieved_sources(mock_llm, mock_search):
    mock_search.return_value = CHUNKS
    mock_llm.get_case_extraction_model.return_value = _mock_model(
        {"answer": "Khader Basha.", "sources": ["petition.pdf", "invented.pdf"]}
    )

    response = client.post("/case-ingestion/query", json={"case_id": "c1", "query": "father?"})

    assert response.status_code == 200
    assert response.json()["data"] == {"answer": "Khader Basha.", "sources": ["petition.pdf"]}
    mock_search.assert_awaited_once_with("father?", case_id="c1")


@patch("src.services.case_ingestion.search_chunks", new_callable=AsyncMock)
@patch("src.services.case_ingestion.xllm_service")
def test_query_not_found_has_no_sources(mock_llm, mock_search):
    mock_search.return_value = CHUNKS
    mock_llm.get_case_extraction_model.return_value = _mock_model(
        {"answer": "Not found in the case documents.", "sources": ["petition.pdf"]}
    )

    response = client.post("/case-ingestion/query", json={"case_id": "c1", "query": "judge?"})

    assert response.json()["data"] == {
        "answer": "Not found in the case documents.",
        "sources": [],
    }


@patch("src.services.case_ingestion.search_chunks", new_callable=AsyncMock, return_value=[])
def test_query_with_no_chunks_skips_llm(mock_search):
    response = client.post("/case-ingestion/query", json={"case_id": "none", "query": "x"})

    assert response.json()["data"] == {
        "answer": "Not found in the case documents.",
        "sources": [],
    }
