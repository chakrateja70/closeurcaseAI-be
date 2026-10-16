import asyncio
import hashlib
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
from src.services.usage_service import record_embedding_usage
from src.utils.helper import build_content_parts

CASE_TEXT_NAME = "case_text"  # document name used for inline case_text
SPARSE_MODEL = "pinecone-sparse-english-v0"
SPARSE_BATCH_SIZE = 96  # hosted sparse model's max inputs per request
UPSERT_BATCH_SIZE = 100  # keeps each request under Pinecone's 2MB limit
# 1.0 = pure dense (semantic), 0.0 = pure sparse (keyword). Sparse scores run ~5-10x larger
# than dense cosine, so alpha > 0.5 is needed to balance them. Tune with scripts/eval_retrieval.py
HYBRID_ALPHA = 0.7
MIN_DENSE_SIMILARITY = 0.2  # drop matches whose dense cosine similarity is below this

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200, chunk_overlap=150, length_function=len, is_separator_regex=False
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
        documents.append((CASE_TEXT_NAME, case_text))

    return documents


def create_chunks(documents: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Split each document separately so every chunk keeps its document_name."""
    return [(name, chunk) for name, text in documents for chunk in text_splitter.split_text(text)]


async def create_embeddings(chunks: list[str]) -> list[list[float]]:
    model = xllm_service.get_embedding_model()
    with openai_errors("embedding"):
        vectors = await model.aembed_documents(chunks)
    record_embedding_usage(model.model, chunks)
    return vectors


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


def chunk_id(case_id: str, doc_name: str, position: int) -> str:
    digest = hashlib.sha256(doc_name.encode()).hexdigest()[:12]
    return f"{case_id}-{digest}-{position}"


def upsert_case_vectors(
    case_id: str,
    chunks: list[tuple[str, str]],
    dense_vectors: list[list[float]],
    sparse_vectors: list[dict],
) -> None:
    index = get_index()
    now = datetime.now(UTC).isoformat()
    try:
        # Extracted text differs run to run, so chunks can't be deduped by content. Re-ingesting a
        # document (same name) replaces that document's chunks; other documents are kept.
        for doc_name in dict.fromkeys(name for name, _ in chunks):
            index.delete(
                filter={"case_id": {"$eq": case_id}, "document_name": {"$eq": doc_name}},
                namespace=CASES_NAMESPACE,
            )

        positions: dict[str, int] = {}
        vectors = []
        for (doc_name, chunk), dense, sparse in zip(
            chunks, dense_vectors, sparse_vectors, strict=True
        ):
            position = positions.get(doc_name, 0)
            positions[doc_name] = position + 1
            vector = {
                "id": chunk_id(case_id, doc_name, position),
                "values": dense,
                "metadata": {
                    "text": chunk,
                    "case_id": case_id,
                    "chunk_index": position,
                    "document_name": doc_name,
                    "created_at": now,
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
    except Exception as e:
        raise ServiceUnavailableAPIException("Could not upsert vectors to Pinecone") from e
    if response.has_errors:
        raise ServiceUnavailableAPIException("Some vectors failed to upsert to Pinecone")


def document_exists(case_id: str, doc_name: str) -> bool:
    """Chunk 0 always exists for an ingested document (ids are derived from its name)."""
    chunk_0 = chunk_id(case_id, doc_name, 0)
    try:
        return chunk_0 in get_index().fetch(ids=[chunk_0], namespace=CASES_NAMESPACE).vectors
    except Exception as e:
        raise ServiceUnavailableAPIException("Could not check existing documents") from e


async def ingest_case(
    case_id: str,
    case_text: str | None = None,
    urls: list[str] | None = None,
    replace: bool = False,
) -> list[str]:
    """Returns the names of documents skipped because they were already ingested."""
    sources = {document_name(u): u for u in urls or []}
    if case_text:
        sources[CASE_TEXT_NAME] = case_text

    skipped: list[str] = []
    if not replace:
        exists = await asyncio.gather(
            *(asyncio.to_thread(document_exists, case_id, name) for name in sources)
        )
        skipped = [name for name, found in zip(sources, exists, strict=True) if found]
    new_urls = [u for name, u in sources.items() if name != CASE_TEXT_NAME and name not in skipped]
    new_text = None if CASE_TEXT_NAME in skipped else case_text
    if not new_urls and not new_text:
        return skipped

    documents = await extract_text(case_text=new_text, urls=new_urls)
    chunks = create_chunks(documents)
    if not chunks:
        raise BadRequestAPIException("No text could be extracted from the case")
    texts = [text for _, text in chunks]
    dense_vectors, sparse_vectors = await asyncio.gather(
        create_embeddings(texts), asyncio.to_thread(sparse_embed, texts, "passage")
    )
    await asyncio.to_thread(upsert_case_vectors, case_id, chunks, dense_vectors, sparse_vectors)
    return skipped


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


async def search_chunks(query: str, case_id: str, top_k: int = 7) -> list[dict]:
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
