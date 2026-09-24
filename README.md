# CloseUrCase AI Backend

FastAPI backend for CloseUrCase AI. Python 3.12, managed with `uv`.

## Setup

```sh
uv venv
.venv/scripts/activate
uv sync
cp .env.example .env   # fill in OPENAI_API_KEY, SWAGGER_USERNAME, SWAGGER_PASSWORD, etc.
```

## Run

```sh
uvicorn main:app --reload   # http://localhost:8000, auto-reload
```

Docs: `http://localhost:8000/docs` (HTTP Basic auth, credentials from `.env`).

## Test & lint

```sh
uv run ruff check --fix .
uv run ruff format .
uv run pytest
```

## Features

- `POST /detection/detect-case` — classify a legal query into a category/subcategory
- `POST /summarization/summarize-case` — summarize a case from text and/or document URLs

See [CLAUDE.md](CLAUDE.md) for architecture and conventions.
