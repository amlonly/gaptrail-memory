"""Own and clean up a local model/API pair under an atomic GPU lock."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("llama-server", "gguf", "bge", "tokenizer"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--model-port", type=int, default=18405)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--lock-dir", type=Path)
    parser.add_argument("--no-auth", action="store_true", help="Loopback development only")
    args = parser.parse_args()
    for name in ("llama_server", "gguf", "bge", "tokenizer"):
        value = getattr(args, name).resolve()
        if not value.exists():
            parser.error(f"Local resource does not exist: {name}")
        setattr(args, name, value)
    if not args.no_auth and not os.getenv("MEMORY_API_KEY"):
        parser.error("Set MEMORY_API_KEY in the environment or explicitly use --no-auth")
    runtime = REPO/".runtime"
    runtime.mkdir(exist_ok=True)
    common = next((p/"competition/research/parallel-seven-20261030/local-model.lock"
        for p in REPO.parents if (p/"competition/research/parallel-seven-20261030").is_dir()), None)
    lock = common or args.lock_dir or runtime/"local-model.lock"
    if common and args.lock_dir and args.lock_dir.resolve()!=common.resolve():
        parser.error("Inside the research workspace the shared GPU lock is mandatory")
    lock = lock.resolve()
    lock.parent.mkdir(parents=True, exist_ok=True)
    for port in (args.model_port, args.api_port):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port))==0:
                parser.error(f"Port {port} is occupied; no existing service will be replaced")
    owner = dict(owner="gaptrail-memory", nonce=uuid4().hex, pid=os.getpid(),
        port=args.model_port, run=str(REPO), requested_utc=datetime.now(timezone.utc).isoformat())
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            print("Waiting for GPU owner to release its lock:", lock, flush=True)
            time.sleep(30)
    owner["acquired_utc"] = datetime.now(timezone.utc).isoformat()
    save(lock/"owner.json", owner)
    save(runtime/"ownership.json", owner)
    children, handles = [], []
    flags = subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    try:
        # Recheck after the wait; ownership of a lock does not free an occupied port.
        for port in (args.model_port, args.api_port):
            with socket.socket() as sock:
                if sock.connect_ex(("127.0.0.1", port))==0:
                    raise RuntimeError(f"Port became occupied while waiting: {port}")
        model_log = (runtime/"model.log").open("ab")
        handles.append(model_log)
        model = subprocess.Popen([str(args.llama_server), "-m", str(args.gguf),
            "--host", "127.0.0.1", "--port", str(args.model_port), "--alias", "gaptrail-qwen",
            "--ctx-size", "8192", "--parallel", "1", "--threads", "6", "--threads-batch", "12",
            "--batch-size", "512", "--ubatch-size", "128", "--split-mode", "none",
            "--gpu-layers", "all", "--flash-attn", "on", "--no-context-shift",
            "--seed", "20261030", "--temp", "0", "--reasoning-budget", "0", "--jinja",
            "--cache-ram", "0", "--no-cache-prompt", "--no-cache-idle-slots"],
            stdout=model_log, stderr=model_log, creationflags=flags)
        children.append(model)
        ready = False
        for _ in range(120):
            if model.poll() is not None:
                raise RuntimeError("Owned local model exited; inspect .runtime/model.log")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.model_port}/health", timeout=2) as response:
                    ready = response.status==200
                if ready:
                    break
            except OSError:
                pass
            time.sleep(1)
        if not ready:
            raise RuntimeError("Owned local model startup timed out")
        env = dict(os.environ, GAPTRAIL_BGE_PATH=str(args.bge), GAPTRAIL_TOKENIZER_PATH=str(args.tokenizer),
            GAPTRAIL_PLANNER_URL=f"http://127.0.0.1:{args.model_port}/v1/chat/completions",
            GAPTRAIL_MODEL_ALIAS="gaptrail-qwen")
        if args.no_auth:
            env["GAPTRAIL_LOCAL_NO_AUTH"] = "1"
        api_log = (runtime/"api.log").open("ab")
        handles.append(api_log)
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "gaptrail.api:app", "--host", "127.0.0.1",
            "--port", str(args.api_port), "--workers", "1"], cwd=REPO, env=env,
            stdout=api_log, stderr=api_log, creationflags=flags)
        children.append(api)
        save(runtime/"processes.json", dict(model_pid=model.pid, api_pid=api.pid, owner_nonce=owner["nonce"]))
        print(f"API starting at http://127.0.0.1:{args.api_port}; Ctrl+C stops only this owned pair.", flush=True)
        while model.poll() is None and api.poll() is None:
            time.sleep(.5)
        raise RuntimeError("An owned child exited; inspect .runtime logs before restarting")
    except KeyboardInterrupt:
        print("Stopping owned processes.", flush=True)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
        for handle in handles:
            handle.close()
        current = json.loads((lock/"owner.json").read_text(encoding="utf-8"))
        if current.get("nonce") != owner["nonce"]:
            raise RuntimeError("GPU owner changed unexpectedly; leave the lock untouched")
        (lock/"owner.json").unlink()
        lock.rmdir()
        save(runtime/"release.json", dict(nonce=owner["nonce"], released_utc=datetime.now(timezone.utc).isoformat()))


if __name__=="__main__":
    main()
