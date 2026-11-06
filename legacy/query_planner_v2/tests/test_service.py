"""CPU-only contract/provenance tests with synthetic history and scripted plans."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import numpy as np
import httpx

from adaptive_evidence.core import Config, MemoryStore
from gaptrail.api import Engine, create_app
from gaptrail.planner import BoundedSearch
from gaptrail.runtime import LocalPlanner


class Encoder:
    identity = "synthetic-cpu-test"
    def encode(self, texts, **kwargs):
        rows = [np.frombuffer(hashlib.sha256(t.encode()).digest(), dtype=np.uint8).astype(np.float32) for t in texts]
        return np.stack([r/np.linalg.norm(r) for r in rows])


class Tokenizer:
    def encode(self, text, **kwargs):
        return text.split()
    def decode(self, ids, **kwargs):
        return " ".join(ids)
    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages).split()


class Runtime:
    def __init__(self, actions=()):
        self.actions = iter(actions)
        self.calls = []
    def complete(self, kind, messages, schema):
        return dict(usage=dict(prompt_tokens=1, completion_tokens=1), choices=[dict(
            finish_reason="stop", message=dict(content=json.dumps(next(self.actions))))]), False
    def close(self):
        pass


def action(kind="search", query="novel bridge", notes=None, support=None):
    return dict(action=kind, query=query, missing="bridge relation", note_ids=notes or [], support=support or [])


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.store = MemoryStore(self.path/"memory.sqlite3", Encoder(), Config(cache_users=1))
        self.store.add(user_id="synthetic", request_id="r", session_id="s", messages=[dict(role="user",
            content=f"Speaker {i} records marker{i}. "+"neutral original context. "*30) for i in range(60)])
        self.index = self.store.index("synthetic")
        self.initial = [dict(id=r["id"], content=self.store.render(r), score=1.) for r in self.index.rows[:10]]

    def tearDown(self):
        self.store.cache.clear()
        self.temp.cleanup()

    def test_new_notes_replace_initial_notes_and_preserve_sources(self):
        runtime = Runtime([action(notes=[1,2,3,4]), action("finish", query="", notes=[11],
            support=[dict(relation="bridge", evidence_id=11, quote="Speaker")])])
        planner = BoundedSearch(self.store, runtime, Tokenizer())
        result = planner.search(user_id="synthetic", query="missing relationship", initial_hits=self.initial)
        self.assertEqual(result[:2], self.initial[:2])
        self.assertEqual(planner.last_trace["note_ids"], [11])
        self.assertNotIn(result[2]["id"], {h["id"] for h in self.initial})
        self.assertIn(result[2]["content"], [self.store.render(r) for r in self.index.rows])
        self.assertLessEqual(sum(len(h["content"]) for h in result), 24000)
        self.assertNotIn("bridge relation", str(result))

    def test_hard_query_bound(self):
        planner = BoundedSearch(self.store, Runtime([action(query=q) for q in ("q1", "q2", "q3")]), Tokenizer())
        planner.search(user_id="synthetic", query="start", initial_hits=self.initial)
        self.assertEqual(planner.last_trace["query_count"], 3)
        self.assertEqual(planner.last_trace["planner_calls"], 3)
        self.assertEqual(planner.last_trace["stop_reason"], "query_budget")

    def test_direct_support_finishes_with_no_extra_query(self):
        planner = BoundedSearch(self.store, Runtime([action("finish", query="", notes=[1],
            support=[dict(relation="fact", evidence_id=1, quote="Speaker 0")])]), Tokenizer())
        self.assertEqual(planner.search(user_id="synthetic", query="fact", initial_hits=self.initial), self.initial)
        self.assertEqual(planner.last_trace["query_count"], 1)

    def test_api_contract_metrics_and_extra_fields(self):
        engine = Engine(self.store, Tokenizer(), lambda: Runtime(), self.path/"metrics.jsonl")
        with patch.dict(os.environ, {"GAPTRAIL_LOCAL_NO_AUTH":"1", "MEMORY_API_KEY":""}):
            with TestClient(create_app(lambda: engine)) as client:
                payload = dict(request_id="one", user_id="one", session_id="one",
                    messages=[dict(role="user", content="The laboratory sample is teal.")])
                self.assertEqual(client.post("/add", json=payload).status_code, 200)
                request = dict(user_id="one", query="What color is the sample?", top_k=5)
                response = client.post("/search", json=request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json()), {"data"})
                self.assertIn("teal", response.json()["data"][0]["content"])
                self.assertEqual(client.post("/search", json={**request,"gold":"forbidden"}).status_code, 422)
        metric = json.loads((self.path/"metrics.jsonl").read_text())
        self.assertEqual(metric["query_count"], 1)
        self.assertEqual(metric["planner_calls"], 0)
        self.assertNotIn("What color", json.dumps(metric))

    def test_local_transport_rejects_remote_or_embedded_credentials(self):
        for url in ("https://example.com/v1/chat/completions", "http://127.0.0.1.evil.test/", "http://u:p@127.0.0.1/"):
            with self.assertRaises(ValueError):
                LocalPlanner(Tokenizer(), url, "test")

    def test_local_transport_preserves_frozen_sampling_and_usage(self):
        requests = []
        messages = [{"role":"user", "content":"synthetic request"}]
        expected = len(Tokenizer().apply_chat_template(messages))
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=dict(model="test", usage=dict(prompt_tokens=expected,
                completion_tokens=1), choices=[dict(finish_reason="stop", message=dict(content="{}"))]))
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            runtime = LocalPlanner(Tokenizer(), "http://127.0.0.1:18405/v1/chat/completions", "test", client)
            _, reused = runtime.complete("Planner", messages, {"type":"object"})
        self.assertFalse(reused)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["temperature"], 0)
        self.assertEqual(requests[0]["seed"], 20261030)
        self.assertEqual(requests[0]["max_tokens"], 512)
        self.assertFalse(requests[0]["chat_template_kwargs"]["enable_thinking"])

    def test_tokenizer_mismatch_fails_without_retry(self):
        sent = []
        def respond(request):
            sent.append(True)
            return httpx.Response(200, json=dict(model="test", usage=dict(prompt_tokens=999),
                choices=[dict(message=dict(content="{}"))]))
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            runtime = LocalPlanner(Tokenizer(), "http://127.0.0.1:18405/v1/chat/completions", "test", client)
            with self.assertRaisesRegex(ValueError, "Tokenizer mismatch"):
                runtime.complete("Planner", [{"role":"user","content":"test"}], {})
        self.assertEqual(len(sent), 1)


if __name__=="__main__":
    unittest.main()
