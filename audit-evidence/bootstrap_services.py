"""
Shared service bootstrap for the FASHORA audit harnesses (S1-S4).

Ensures the four FastAPI backends are listening before tests run; anything
that is down is started with that agent's own .venv (detached, PYTHONPATH set
to the repo root) and waited on until healthy. Services that were already
running are left exactly as found; services this helper started are stopped
again at process exit unless the caller keeps the returned handle alive.

Usage from a harness:
    from bootstrap_services import ensure_services
    ensure_services(ports=(8001,))                      # S1
    ensure_services(ports=(8001, 8002, 8003, 8004))     # S3/S4

CLI test:  python bootstrap_services.py [port ...]
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# port -> (agent dir, health path, extra wait budget seconds)
SERVICES = {
    8001: ("agents/agent1_wardrobe", "/api/health", 60),
    8002: ("agents/agent2_retrieval", "/health", 240),   # BM25+Chroma+embeddings load
    8003: ("agents/agent3_budget", "/budget/health", 60),
    8004: ("agents/agent4_decision", "/decision/health", 60),
}

IS_WIN = os.name == "nt"
DOWNED = []  # popen handles we created, for optional cleanup


def _python_for(agent_dir):
    cand = (os.path.join(agent_dir, ".venv", "Scripts", "python.exe"),
            os.path.join(agent_dir, ".venv", "bin", "python"))
    for c in cand:
        if os.path.exists(c):
            return c
    raise RuntimeError(f"No .venv python found under {agent_dir} — run scripts/setup first")


def healthy(port, path, timeout=5):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def start(port):
    agent_rel, health_path, wait_budget = SERVICES[port]
    agent_dir = os.path.join(REPO_ROOT, agent_rel)
    env = dict(os.environ, PYTHONPATH=REPO_ROOT)
    kwargs = {}
    if IS_WIN:
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP -> survives this harness
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [_python_for(agent_dir), "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=agent_dir, env=env,
        stdout=open(os.path.join(REPO_ROOT, "audit-evidence", f".bootstrap-{port}.log"), "a"),
        stderr=subprocess.STDOUT, **kwargs)
    t0 = time.time()
    while time.time() - t0 < wait_budget:
        if healthy(port, health_path):
            print(f"[bootstrap] service on :{port} started and healthy ({round(time.time()-t0)}s)")
            DOWNED.append(proc)
            return proc
        if proc.poll() is not None:
            raise RuntimeError(f"service on :{port} died during startup — see audit-evidence/.bootstrap-{port}.log")
        time.sleep(2)
    raise RuntimeError(f"service on :{port} not healthy within {wait_budget}s — see audit-evidence/.bootstrap-{port}.log")


def ensure_services(ports=(8001, 8002, 8003, 8004)):
    procs = {}
    for port in ports:
        agent_rel, health_path, _ = SERVICES[port]
        if healthy(port, health_path):
            print(f"[bootstrap] :{port} already running (left untouched)")
            continue
        print(f"[bootstrap] :{port} down — starting {agent_rel} ...")
        procs[port] = start(port)
    return procs


def stop_started():
    """Stop only the services this helper started (never pre-existing ones)."""
    for proc in DOWNED:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    ports = tuple(int(a) for a in sys.argv[1:]) or (8001, 8002, 8003, 8004)
    ensure_services(ports)
    print("[bootstrap] all required services healthy:")
    for p in ports:
        print(f"  :{p} {SERVICES[p][1]} -> {healthy(p, SERVICES[p][1])}")
