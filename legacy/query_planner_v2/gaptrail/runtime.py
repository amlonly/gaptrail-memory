"""Single-attempt, loopback-only local planner transport."""
import time
from urllib.parse import urlsplit

import httpx


class LocalPlanner:
    def __init__(self, tokenizer, endpoint, model, client=None):
        url = urlsplit(endpoint)
        if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"}
                or url.username or url.password or url.query or url.fragment):
            raise ValueError("Planner endpoint must be a plain loopback HTTP URL")
        self.tokenizer, self.endpoint, self.model = tokenizer, endpoint, model
        self.client = client or httpx.Client(timeout=240, trust_env=False)
        self.owns_client = client is None
        self.calls = []

    def complete(self, kind, messages, output_schema):
        if kind != "Planner":
            raise ValueError("This service only invokes a retrieval planner")
        ids = self.tokenizer.apply_chat_template(messages, tokenize=True,
            add_generation_prompt=True, enable_thinking=False)
        if hasattr(ids, "keys"):
            ids = ids["input_ids"]
        expected = len(ids[0]) if ids and isinstance(ids[0], list) else len(ids)
        if expected > 4096:
            raise ValueError("Planner input exceeds 4096 tokens")
        payload = dict(model=self.model, messages=messages, temperature=0,
            max_tokens=512, seed=20261030,
            chat_template_kwargs={"enable_thinking": False}, reasoning_effort="none",
            response_format={"type": "json_schema", "json_schema": {
                "name": "native_judge", "strict": True, "schema": output_schema}})
        started = time.monotonic()
        response = self.client.post(self.endpoint, json=payload)
        response.raise_for_status()
        value = response.json()
        if value.get("model") != self.model:
            raise ValueError("Local model alias mismatch")
        if value["usage"]["prompt_tokens"] != expected:
            raise ValueError("Tokenizer mismatch or silent input truncation")
        if not isinstance(value["choices"][0]["message"]["content"], str):
            raise ValueError("Planner content missing")
        self.calls.append(dict(seconds=time.monotonic()-started, usage=value["usage"]))
        return value, False

    def close(self):
        if self.owns_client:
            self.client.close()
