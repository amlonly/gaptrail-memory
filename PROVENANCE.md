# Source provenance

GapTrail Memory 0.1.0 packages direction 05, bounded multi-turn query planning.

The `adaptive_evidence/` modules are byte-identical copies of the required retrieval dependency closure from the exact official SourceTrail / Context Weave 0.32.0 archive, SHA256 `bff4443ee3cbdf4a5e320dfa56fb8e65ca7775d857550c4112de7ddb7a9c74fa`. The original MIT license and copyright are retained. The old upstream API and remote embedding adapter are not entry points in this package and were omitted.

`gaptrail/planner.py` is byte-identical to the frozen `v2-novel-gaps/planner_v2.py`. Its research protocol SHA256 is `96d5582fef1e95329a06417f9bb1b780aa45767821012473527a1b7f2f3ab70f`. The exact dependency and planner file hashes are in `SOURCE_MANIFEST.json`.

The independent API, local transport, launcher, tests and documentation are publication packaging. They were CPU-tested separately after the research run; no new benchmark accuracy is attributed to the packaging. API result content remains original retrieval evidence. Answer and Judge are external responsibilities.

No graph selection, ColBERT, global-user-facts, state lifecycle or procedure modules from the other research directions are added. Only the source-grounded retrieval incumbent and the bounded query planner are used.

Dataset records, historical conversations, reference answers, model answers, rubric prompts, response caches, databases, model weights, machine logs and authentication material are excluded from publication. Research summaries retain aggregate outcomes and public case identifiers only.
