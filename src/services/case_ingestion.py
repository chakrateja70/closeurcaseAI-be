import asyncio
import math
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from langchain_core.language_models import LanguageModelInput
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone.models.inference.embed import SparseEmbedding

from src.core.exceptions import (
    BadRequestAPIException,
    ServiceUnavailableAPIException,
    openai_errors,
    parse_json_content,
)
from src.db.pinecone import CASES_NAMESPACE, get_index, pinecone_client
from src.prompts.case_ingestion import (
    ANSWER_SYSTEM_PROMPT,
    EXTRACT_SYSTEM_PROMPT,
    NOT_FOUND_ANSWER,
)
from src.services.llm_service import xllm_service
from src.utils.helper import build_content_parts

SPARSE_MODEL = "pinecone-sparse-english-v0"
SPARSE_BATCH_SIZE = 96  # hosted sparse model's max inputs per request
UPSERT_BATCH_SIZE = 100  # keeps each request under Pinecone's 2MB limit
# 1.0 = pure dense (semantic), 0.0 = pure sparse (keyword). Sparse scores run ~5-10x larger
# than dense cosine, so alpha > 0.5 is needed to balance them. Tune with scripts/eval_retrieval.py
HYBRID_ALPHA = 0.9
MIN_DENSE_SIMILARITY = 0.3  # drop matches whose dense cosine similarity is below this

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000, chunk_overlap=200, length_function=len, is_separator_regex=False
)


def document_name(url: str) -> str:
    # Only the filename is logged/stored: full URLs may carry signed access tokens.
    # unquote: Firebase-style URLs encode folders as %2F, e.g. teja%2FWP%20No.pdf -> WP No.pdf
    return Path(unquote(urlparse(url).path)).name or "document"


async def extract_from_url(client: httpx.AsyncClient, url: str) -> str:
    content_parts = await build_content_parts(client, case_text=None, urls=[url])
    messages: LanguageModelInput = [
        ("system", EXTRACT_SYSTEM_PROMPT),
        ("user", content_parts),
    ]

    model = xllm_service.get_case_extraction_model()
    with openai_errors("case extraction"):
        response = await model.ainvoke(messages)

    if not isinstance(response.content, str):
        raise BadRequestAPIException("Case extraction model returned an unexpected response format")
    if response.response_metadata.get("finish_reason") == "length":
        raise BadRequestAPIException(
            f"Document too long to extract completely: {document_name(url)}"
        )
    return response.content


async def extract_text(
    case_text: str | None = None, urls: list[str] | None = None
) -> list[tuple[str, str]]:
    """Returns (document_name, text) per source so each chunk can cite its document."""
    documents = []
    if urls:
        async with httpx.AsyncClient(timeout=10) as client:
            results = await asyncio.gather(*(extract_from_url(client, str(u)) for u in urls))
        documents = [
            (document_name(str(url)), text) for url, text in zip(urls, results, strict=True)
        ]

    if case_text:
        documents.append(("case_text", case_text))

    return documents


def create_chunks(documents: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Split each document separately so every chunk keeps its document_name."""
    return [(name, chunk) for name, text in documents for chunk in text_splitter.split_text(text)]


async def create_embeddings(chunks: list[str]) -> list[list[float]]:
    model = xllm_service.get_embedding_model()
    with openai_errors("embedding"):
        return await model.aembed_documents(chunks)


def sparse_embed(texts: list[str], input_type: str) -> list[dict]:
    """Keyword vectors from Pinecone's hosted sparse model. Its corpus-wide weights make
    scores comparable across cases; input_type is "passage" for chunks, "query" for queries."""
    vectors = []
    try:
        for i in range(0, len(texts), SPARSE_BATCH_SIZE):
            result = pinecone_client.inference.embed(
                model=SPARSE_MODEL,
                inputs=texts[i : i + SPARSE_BATCH_SIZE],
                parameters={"input_type": input_type, "truncate": "END"},
            )
            # the sparse model only returns SparseEmbedding; the SDK types it as dense | sparse
            vectors += [
                {"indices": e.sparse_indices, "values": e.sparse_values}
                for e in result.data
                if isinstance(e, SparseEmbedding)
            ]
    except Exception as e:
        raise ServiceUnavailableAPIException("Could not create sparse embeddings") from e
    return vectors


def hybrid_scale(dense: list[float], sparse: dict) -> tuple[list[float], dict]:
    """Weight dense vs sparse so neither dominates the dotproduct score."""
    return (
        [v * HYBRID_ALPHA for v in dense],
        {
            "indices": sparse["indices"],
            "values": [v * (1 - HYBRID_ALPHA) for v in sparse["values"]],
        },
    )


def upsert_case_vectors(
    case_id: str,
    chunks: list[tuple[str, str]],
    dense_vectors: list[list[float]],
    sparse_vectors: list[dict],
) -> None:
    index = get_index()
    now = datetime.now(UTC).isoformat()
    try:
        # Re-ingest keeps the case's original created_at; only updated_at moves.
        existing = index.fetch(ids=[f"{case_id}-0"], namespace=CASES_NAMESPACE).vectors
        first = existing.get(f"{case_id}-0")
        created_at = (first.metadata or {}).get("created_at", now) if first else now

        vectors = []
        for i, ((doc_name, chunk), dense, sparse) in enumerate(
            zip(chunks, dense_vectors, sparse_vectors, strict=True)
        ):
            vector = {
                "id": f"{case_id}-{i}",
                "values": dense,
                "metadata": {
                    "text": chunk,
                    "case_id": case_id,
                    "chunk_index": i,
                    "document_name": doc_name,
                    "created_at": created_at,
                    "updated_at": now,
                },
            }
            if sparse["indices"]:  # Pinecone rejects empty sparse vectors
                vector["sparse_values"] = sparse
            vectors.append(vector)

        response = index.upsert(
            vectors=vectors,
            namespace=CASES_NAMESPACE,
            batch_size=UPSERT_BATCH_SIZE,
            show_progress=False,
        )
        # Re-ingest may produce fewer chunks: drop the old tail after the new chunks land.
        index.delete(
            filter={"case_id": {"$eq": case_id}, "chunk_index": {"$gte": len(chunks)}},
            namespace=CASES_NAMESPACE,
        )
    except Exception as e:
        raise ServiceUnavailableAPIException("Could not upsert vectors to Pinecone") from e
    if response.has_errors:
        raise ServiceUnavailableAPIException("Some vectors failed to upsert to Pinecone")


async def ingest_case(
    case_id: str, case_text: str | None = None, urls: list[str] | None = None
) -> None:
    documents = await extract_text(case_text=case_text, urls=urls)
    chunks = create_chunks(documents)
    if not chunks:
        raise BadRequestAPIException("No text could be extracted from the case")
    texts = [text for _, text in chunks]
    dense_vectors, sparse_vectors = await asyncio.gather(
        create_embeddings(texts), asyncio.to_thread(sparse_embed, texts, "passage")
    )
    await asyncio.to_thread(upsert_case_vectors, case_id, chunks, dense_vectors, sparse_vectors)


async def delete_case(case_id: str) -> None:
    try:
        await asyncio.to_thread(
            get_index().delete,
            filter={"case_id": {"$eq": case_id}},
            namespace=CASES_NAMESPACE,
        )
    except Exception as e:
        raise ServiceUnavailableAPIException("Could not delete case vectors from Pinecone") from e


def cosine_similarity(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


async def search_chunks(query: str, case_id: str, top_k: int = 15) -> list[dict]:
    """Hybrid search within one case: alpha-weighted dense + sparse, fused server-side.
    Matches whose dense cosine similarity is below MIN_DENSE_SIMILARITY are dropped."""
    dense_vectors, sparse_vectors = await asyncio.gather(
        create_embeddings([query]), asyncio.to_thread(sparse_embed, [query], "query")
    )
    dense, sparse = hybrid_scale(dense_vectors[0], sparse_vectors[0])

    try:
        results = await asyncio.to_thread(
            get_index().query,
            vector=dense,
            sparse_vector=sparse if sparse["indices"] else None,
            top_k=top_k,
            namespace=CASES_NAMESPACE,
            filter={"case_id": {"$eq": case_id}},
            include_metadata=True,
            include_values=True,  # hybrid score mixes in sparse; cosine needs raw dense values
        )
    except Exception as e:
        raise ServiceUnavailableAPIException("Could not query Pinecone") from e

    chunks = []
    for match in results.matches:
        similarity = cosine_similarity(dense_vectors[0], match.values)
        if similarity < MIN_DENSE_SIMILARITY:
            continue
        metadata = match.metadata or {}
        chunks.append(
            {
                "id": match.id,
                "score": match.score,
                "similarity": round(similarity, 4),
                "text": metadata.get("text"),
                "document_name": metadata.get("document_name"),
            }
        )
    return chunks


async def answer_query(case_id: str, query: str) -> dict:
    """Retrieve the case's relevant chunks and answer from them, citing only used sources."""
    chunks = await search_chunks(query, case_id=case_id)
    if not chunks:
        return {"answer": NOT_FOUND_ANSWER, "sources": []}

    context = "\n\n".join(f"[{c['document_name']}]\n{c['text']}" for c in chunks)
    messages: LanguageModelInput = [
        ("system", ANSWER_SYSTEM_PROMPT),
        ("user", f"Context:\n{context}\n\nQuestion: {query}"),
    ]
    model = xllm_service.get_case_extraction_model().bind(response_format={"type": "json_object"})
    with openai_errors("answer"):
        response = await model.ainvoke(messages)

    result = parse_json_content(response.content, "answer")

    answer = result.get("answer") or NOT_FOUND_ANSWER
    if answer == NOT_FOUND_ANSWER:
        return {"answer": answer, "sources": []}
    # Keep only cited names that were really retrieved, so the model can't invent a source.
    retrieved = {c["document_name"] for c in chunks}
    return {"answer": answer, "sources": [s for s in result.get("sources", []) if s in retrieved]}
