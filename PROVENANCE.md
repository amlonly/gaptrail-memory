# Graph release identity and version notes

The graph release uses direct-original-blocks V4. Its fixed implementation commit is `18bbf3d499d5fd3afd8794f16fd2d3bdbceb42aa`, and its frozen protocol SHA256 is `8b314bc69c6ec48006abd42c0155602c29132b865298272c71ddb43367c33fdd`. Applicable MIT licenses and copyright notices are retained in the release and its canonical archive.

The canonical `frozen-runtime.tar.gz` preserves all 40 implementation/dependency files byte-for-byte; Git text display can normalize line endings. Their identities are listed in `releases/graph-v4-m05/M05_MANIFEST.json`. The added `m05_graph_entry.py` verifies those hashes at startup, selects the graph mode, fixes the evidence budget and separate database path, and replaces only the health metadata endpoint. Add/Search functions, ranking, source slices and response ordering remain the frozen implementation. No Qwen or other generative model is invoked by the memory service. Embeddings use text-embedding-v4; platform Answer/Judge are unchanged.

The Full runtime is fixed at commit `8b39b233b7d0d6046ba7aab58abc009c25347ab0`. Subsequent root README and run-guide changes are documentation updates; release files and the canonical archive remain unchanged.

Earlier v2 packaging remains historical research code. Its file manifest, research results and licenses are recorded separately; its accuracy is not assigned to the graph release. Evaluation inputs, answers, private result details, secrets, databases and private user data are not distributed.
