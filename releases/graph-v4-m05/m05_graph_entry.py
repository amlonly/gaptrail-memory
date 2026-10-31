"""GapTrail deployment metadata; frozen Add/Search functions remain unchanged."""
import hashlib,json,os
from pathlib import Path
from fastapi import Depends
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'M05_MANIFEST.json').read_text())
for name,expected in manifest['files_sha256'].items():
 if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Frozen graph source mismatch')
os.environ['AE_MODE']='query_document_block_graph'
os.environ['AE_CONTEXT_CHARS']='24000'
os.environ['AE_DATABASE']='/var/lib/memory-lab/m05/graph-v4-8b314bc69c6e/memory.sqlite3'
from adaptive_evidence import api as native
app=native.app
app.router.routes[:]=[r for r in app.router.routes if getattr(r,'path',None)!='/health']
@app.get('/health')
def health(store=Depends(native.get_store)):
 return dict(status='ok',system='GapTrail Memory',version='v0.35',candidate_id='graph-v4-m05-8b314bc69c6e',
  source_protocol_sha256=manifest['graph_protocol_sha256'],source_files_verified=len(manifest['graph_files_sha256']),
  search_strategy=os.environ['AE_MODE'],embedding=getattr(store.encoder,'model','unknown'),
  generative_llm_calls_in_memory_service=0,search_planner='none',add_llm='none',
  answer_owner='external_evaluator',judge_owner='external_evaluator',context_chars=store.config.context_chars)
