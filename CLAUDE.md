# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

FastAPI backend for CloseUrCase AI. Python 3.12, managed with `uv`.

## Layout

- `main.py` — app entry; disables default `/docs`/`/redoc` and remounts them behind auth via `src/core/security.py`; mounts `src/router.py`
- `src/router.py` — aggregates all API routers under the `/ai` prefix (so every feature route is `/ai/<feature>/<action>`; `/` and the docs pages are outside it)
- `src/api/` — route modules (one `APIRouter` per feature, e.g. `case_detection.py`); response bodies follow `{status_code, message, data}`. Features: case detection, case summarization, case ingestion (ingest + RAG `query`), counter generation (affidavit → per-paragraph counters with legal basis)
- `src/prompts/` — prompt templates per feature, paired 1:1 with `src/api/` and `src/services/` modules
- `src/services/` — business logic / LLM calls, built on `langchain_openai.ChatOpenAI` via `llm_service.py` (task-specific model getters, e.g. `get_detection_model`, `get_summarization_model`). Every chat getter sets a per-task `prompt_cache_key` for OpenAI prompt caching; `get_counter_generation_model` uses the Responses API (`use_responses_api`, reasoning effort, verbosity), so its replies are block lists — read `response.text`, and truncation shows as `response_metadata["status"] == "incomplete"`. `get_embedding_model` returns `OpenAIEmbeddings`, which emits no LangChain callbacks (not traced by Langfuse)
- `src/services/langfuse_service.py` — optional Langfuse tracing; `get_langfuse_callbacks()` returns `[]` when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` aren't set, passed into every `ChatOpenAI` via `llm_service.py`
- `src/db/pinecone.py` — Pinecone client + index setup (one index, namespace `cases`); each record holds dense (OpenAI embedding) and sparse (Pinecone hosted sparse model) vectors for hybrid search, tuned by `HYBRID_ALPHA` / `MIN_DENSE_SIMILARITY` in `src/services/case_ingestion.py`
- `src/utils/helper.py` — shared request/file helpers (e.g. fetching + size-capping remote images/documents for LLM input parts)
- `src/config/settings.py` — configuration (env vars from `.env`; keep `.env.example` in sync); required vars raise at import time if missing
- `src/core/exceptions.py` — shared `HTTPException` subclasses (`BadRequestAPIException`, `UnauthorizedAPIException`, `TooManyRequestsAPIException`, `ServiceUnavailableAPIException`, `GatewayTimeoutAPIException`) plus the `openai_errors` / `parse_json_content` LLM helpers, all rendering the same `{status_code, status_message, error_message}` envelope. Any exception a service or function needs to raise belongs here — add a new subclass rather than raising ad hoc/raw exceptions in feature code.
- `src/core/security.py` — HTTP Basic auth (`SWAGGER_USERNAME`/`SWAGGER_PASSWORD`) gating `/docs`, `/redoc`, `/openapi.json`
- `master_data/` — static JSON reference data (e.g. `case_detection.json`'s category/subcategory taxonomy) loaded once at module import by the matching service, not per-request
- `tests/` — pytest tests (`fastapi.testclient.TestClient`); mock the LLM at `xllm_service` in the service module being tested (e.g. `@patch("src.services.case_detection.xllm_service")`), not at `llm_service` itself

New feature route: add a module in `src/api/`, a matching module in `src/services/` (and `src/prompts/` if it calls an LLM), include the router in `src/router.py`. Don't add or update tests unless asked — but existing tests must still pass.

## Commands

```sh
uv sync                              # install deps (incl. dev)
uv run python main.py                # run dev server on :8000 (reload)
uv add <pkg> / uv add --dev <pkg>    # add deps (don't edit requirements.txt by hand)
uv run pytest tests/test_x.py::test_y  # run a single test
```

## Quality checks — run before finishing any change

```sh
uv run ruff check --fix .            # lint (config in pyproject.toml)
uv run ruff format .                 # format
uv run pytest                        # tests + coverage -> coverage.xml
```

All three must pass. Don't silence ruff rules with `# noqa` unless there's a real reason.

## SonarQube

Config: `sonar-project.properties` (reads `coverage.xml` and `ruff-report.json`).

```sh
uv run pytest
uv run ruff check . --output-format json -o ruff-report.json --exit-zero
docker run --rm -e SONAR_HOST_URL=<url> -e SONAR_TOKEN=<token> \
  -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli
```

Set `SONAR_HOST_URL` / `SONAR_TOKEN` in your environment; never commit them. Fix new Sonar issues (bugs, vulnerabilities, code smells) before merging.

## Conventions

- Keep this file current: when a code change adds or alters a feature, module, endpoint, setting, or convention that a future reader would otherwise miss, update CLAUDE.md in the same change. Skip it for changes that add no information (bug fixes, renames already reflected here, formatting).
- No `print` or `logging` calls in app code (`main.py`, `src/`).
- Secrets only via `.env` (git-ignored); never hardcode keys.
- Line length 100, imports sorted by ruff (`I` rule).
- LLM calls go through `xllm_service` getters (never instantiate `ChatOpenAI` directly), request structured output with `.bind(response_format={"type": "json_object"})`, wrap `model.ainvoke(...)` in `with openai_errors("<model name>"):` and parse JSON responses with `parse_json_content(...)` (both in `src/core/exceptions.py`) — don't hand-roll the `openai.*Error` mapping.
