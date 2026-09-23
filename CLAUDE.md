# CLAUDE.md

FastAPI backend for CloseUrCase AI. Python 3.12, managed with `uv`.

## Layout

- `main.py` — app entry; mounts `src/router.py`
- `src/router.py` — aggregates all API routers
- `src/api/` — route modules (one `APIRouter` per feature, e.g. `case_detection.py`)
- `src/prompts/` — prompt templates per feature, paired 1:1 with `src/api/` and `src/services/` modules
- `src/services/` — business logic / LLM calls, built on `langchain_openai.ChatOpenAI` via `llm_service.py` (task-specific model getters, e.g. `get_detection_model`, `get_summarization_model`)
- `src/config/settings.py` — configuration (env vars from `.env`; keep `.env.example` in sync); required vars raise at import time if missing
- `src/core/exceptions.py` — shared exceptions (currently empty, reserved for future use)
- `tests/` — pytest tests (`fastapi.testclient.TestClient`)

New feature route: add a module in `src/api/`, a matching module in `src/services/` (and `src/prompts/` if it calls an LLM), include the router in `src/router.py`, add a test in `tests/`.

## Commands

```sh
uv sync                              # install deps (incl. dev)
uv run python main.py                # run dev server on :8000 (reload)
uv add <pkg> / uv add --dev <pkg>    # add deps (don't edit requirements.txt by hand)
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

- Secrets only via `.env` (git-ignored); never hardcode keys.
- Line length 100, imports sorted by ruff (`I` rule).
