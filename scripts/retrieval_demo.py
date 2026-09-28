import asyncio
import json

from src.services.case_ingestion import search_chunks
from src.services.llm_service import xllm_service

NOT_FOUND = "Not found in the case documents."

ANSWER_PROMPT = """You are a legal case assistant. Answer the question using ONLY the context.
Each context block starts with its source document name in [brackets].

Rules:
- Give a direct, simple answer in plain language: 1-3 short sentences, no preamble.
- Do not add facts that are not in the context.
- "sources": only the document names you actually took the answer from.
- If the context does not contain the answer, set "answer" to exactly "{not_found}"
  and "sources" to [].

Respond in JSON: {{"answer": "...", "sources": ["document name", ...]}}

Context:
{context}

Question: {question}"""


async def main():
    query = "where do petitioner live"
    chunks = await search_chunks(query, case_id="feroz", top_k=15)
    if not chunks:
        print({"answer": NOT_FOUND, "sources": []})
        return

    context = "\n\n".join(f"[{c['document_name']}]\n{c['text']}" for c in chunks)
    model = xllm_service.get_case_extraction_model().bind(response_format={"type": "json_object"})
    response = await model.ainvoke(
        ANSWER_PROMPT.format(not_found=NOT_FOUND, context=context, question=query)
    )
    result = json.loads(response.content)

    answer = result.get("answer") or NOT_FOUND
    retrieved = {c["document_name"] for c in chunks}
    # Keep only cited names that were really retrieved; none when nothing was found.
    cited = [s for s in result.get("sources", []) if s in retrieved]
    print({"answer": answer, "sources": [] if answer == NOT_FOUND else cited})


asyncio.run(main())
