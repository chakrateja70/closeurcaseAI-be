"""Load test for the case-detection and case-summarization endpoints.

Run against an already-running server (uvicorn main:app --reload):

    uv run locust -f loadtests/locustfile.py --host http://localhost:8000

Then open http://localhost:8089 to configure users/spawn-rate and start.
Headless example:

    uv run locust -f loadtests/locustfile.py --host http://localhost:8000 \
        --headless -u 10 -r 2 -t 1m

Note: these endpoints call the real OpenAI API — each request is a billed LLM
call, so keep user counts modest unless you intend to spend on it.
"""

from itertools import cycle

from locust import HttpUser, between, task

DETECT_QUERIES = [
    "My landlord is refusing to return my security deposit after eviction.",
    "I received a notice for a cheque bounce case under Section 138.",
    "Someone hacked my social media account and is impersonating me.",
]

SAMPLE_CASE_TEXT = (
    "Plaintiff filed a civil suit seeking recovery of Rs. 5,00,000 against the defendant "
    "for breach of a supply contract dated 12 Jan 2023."
)


class CaseApiUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self._queries = cycle(DETECT_QUERIES)

    @task(2)
    def detect_case(self):
        self.client.post(
            "/detection/detect-case",
            json={"query": next(self._queries)},
            name="/detection/detect-case",
        )

    @task(1)
    def summarize_case(self):
        self.client.post(
            "/summarization/summarize-case",
            json={"case_text": SAMPLE_CASE_TEXT},
            name="/summarization/summarize-case",
        )
