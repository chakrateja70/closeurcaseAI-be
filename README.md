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

## Load testing

```sh
# server must already be running (see Run above)
uv run locust -f loadtests/locustfile.py --host http://localhost:8000
```

Open `http://localhost:8089` to set users/spawn rate and start, or run headless with `--headless -u 10 -r 2 -t 1m`. Each request calls the real OpenAI API — this costs money, so keep user counts modest.

## Features

- `POST /detection/detect-case` — classify a legal query into a category/subcategory
- `POST /summarization/summarize-case` — summarize a case from text and/or document URLs

See [CLAUDE.md](CLAUDE.md) for architecture and conventions.



sonarqube:

docker ps -a
docker run -d --name sonarqube-testing -p 9000:9000 sonarqube:community
