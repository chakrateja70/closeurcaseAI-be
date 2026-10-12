# CloseUrCase AI Backend

## What this project is

CloseUrCase is a legal-assistance platform. This repository is its **AI service**: a FastAPI backend that turns legal documents and user descriptions into structured, useful output using large language models (LLMs).

The platform has three parts:

1. **Frontend**: what the user sees. It collects the user's query and uploaded documents.
2. **Main backend**: handles user authentication, accounts, case records, and file uploads. It stores files and produces a URL for each one.
3. **AI service (this repo)**: receives text and document URLs from the main backend, runs the AI work, and returns structured results. It holds no user accounts and does not store uploaded files.

Keeping the AI work in its own service means AI costs, latency, and failures stay isolated from the core application, and it can be scaled or changed separately.

## What it does

The service offers four capabilities.

**Case detection.** A user describes a problem in plain words ("my landlord won't return my deposit"). The service classifies it into a category and subcategory from a fixed legal taxonomy kept in `master_data/`. If nothing fits, it returns an explicit "other" category rather than guessing.

**Case summarization.** Given the text of a case and/or documents (PDFs, images), it produces a short summary and a list of key points. Documents are passed directly to the model as input, so scanned pages and images can be read without a separate OCR step.

**Case Q&A (retrieval-augmented generation).** A case's documents are split into chunks, converted to vectors, and stored in a vector database, tagged with the case's ID. Later, a question about that case retrieves the most relevant chunks and the model answers using only those, returning the answer along with its sources. This lets the system answer from long case files that would not fit in a single prompt, and keeps answers grounded in the actual documents.

**Counter-argument generation.** Given an affidavit, the service identifies the applicable law regime, then drafts a counter-argument for each numbered paragraph, citing the legal basis (acts and provisions) and relevant case references. Items the model is unsure of are flagged `needs_verification` so a lawyer knows what to check. This is an assistive draft, not legal advice.

## How it works (theory)

### Prompting and structured output

Each capability has its own prompt template. The model is asked to reply in JSON, which the service parses and validates, so downstream systems always receive predictable fields instead of free text. Failures from the model provider (rate limits, timeouts, bad JSON) are translated into consistent error responses.

### Hybrid search

Case Q&A uses two kinds of vectors per chunk:

- **Dense vectors** (OpenAI embeddings) capture meaning, so a question matches text that says the same thing in different words.
- **Sparse vectors** capture exact terms, such as section numbers, names, and dates, which matter a lot in legal text.

Search blends both, with a weight (`HYBRID_ALPHA`) controlling the balance, and a minimum similarity threshold that discards weak matches. This beats either method alone on legal documents.

### Parallel generation and prompt caching

Counter generation is slow if done in one pass over a long affidavit. It runs in two steps: a first call finds the law regime and the paragraph numbers, then one call per paragraph runs in parallel, with a cap on concurrency. Every call starts with the same system prompt and affidavit, and puts the task-specific text last. OpenAI caches that shared prefix, so after the first call the affidavit is read at lower cost and latency.

### Model choice

Different tasks use different models, matched to difficulty and cost: a small, fast model for classification, mid-size models for summarization and extraction, and a stronger reasoning model for counter-arguments. An embedding model handles vectors. Model names are set in one configuration file.

### Observability

Optional Langfuse tracing records each LLM call (inputs, outputs, latency, cost) for debugging and monitoring. It switches on automatically when its keys are provided.

### Evaluation

Answer quality for Q&A is measured offline, not by guesswork. A question-and-answer dataset with known correct answers is run through the real production retrieval and answer code, then scored for retrieval quality and with RAGAS metrics (such as faithfulness and answer relevance). This makes it possible to tune search settings and prompts and see whether a change actually helped.

## Design principles

- **Stateless service.** Documents arrive as URLs and are fetched on demand. Only the vector index holds case data, and it can be deleted per case.
- **Consistent contract.** Every response uses the same `status_code / message / data` shape, and every error uses one envelope.
- **Fail early on bad input.** Requests are validated on arrival (text length, number of documents), and remote files over **15 MB** are refused. File-size limits should be enforced at upload time by the main backend and the frontend too; this service's cap is the last line of defence.
- **Secrets stay out of code.** Keys come from environment variables. The service refuses to start if a required one is missing.
- **Protected docs.** The interactive API docs are behind HTTP Basic auth.
- **Cost awareness.** Prompt caching, per-task model sizing, and concurrency caps keep LLM spend predictable.

## Tech stack

FastAPI and uvicorn, LangChain with OpenAI (chat and embeddings), Pinecone (vector store), Langfuse (tracing), RAGAS (evaluation), pytest, ruff, locust (load testing), SonarQube (code quality).

## Getting started

```sh
uv venv
.venv/scripts/activate
uv sync
cp .env.example .env     # fill in the keys
uv run python main.py    # http://localhost:8000
```

Required settings: `OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `SWAGGER_USERNAME`, `SWAGGER_PASSWORD`. Optional: Langfuse keys for tracing, SonarQube host/token for scans.

Interactive API docs: `http://localhost:8000/docs` (Basic auth).

## Quality and testing

```sh
uv run ruff check --fix .
uv run ruff format .
uv run pytest
```

Other tooling: RAG evaluation scripts in `scripts/` (results in `evaluation_results/`), a locust load test in `loadtests/` (it calls the real OpenAI API and costs money), and SonarQube via `sonar-project.properties`.

## Further reading

[CLAUDE.md](CLAUDE.md) describes the code structure, endpoints, and coding conventions in detail.
