from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datetime import datetime, timezone
import time

from app.challenge import load_challenge
from scripts.capture_evidence import render_html_file_png, render_multi_cmd_png

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    challenge = load_challenge(REPO_ROOT / "config" / "challenge.json")
    print(f"Loaded Challenge: {challenge.challenge_id} | Cohort: {challenge.cohort} | Incident: {challenge.incident}")

    # 1. Disable all incidents first and send 1 warm-up request so Langfuse prompt cache is warm
    with httpx.Client(timeout=15.0) as client:
        for name in ("rag_slow", "tool_fail", "cost_spike"):
            client.post(f"{BASE_URL}/incidents/{name}/disable")
        client.post(
            f"{BASE_URL}/chat",
            json={"user_id": "warmup", "session_id": "warmup", "feature": "qa", "message": "Warmup cache"},
        )

    # 2. Backup existing logs outside repo so CP3 log starts clean
    if LOG_PATH.exists():
        shutil.move(str(LOG_PATH), str(REPO_ROOT.parent / "logs-before-cp3.jsonl"))

    # 3. Run baseline load test in CP3 window
    print("Running CP3 baseline workload...")
    subprocess.run([sys.executable, "scripts/load_test.py"], cwd=REPO_ROOT, check=True)

    # Wait until next minute boundary so baseline and incident appear as two distinct minute buckets on the timeline
    now_sec = datetime.now(timezone.utc).second
    wait_sec = (60 - now_sec) + 1
    if wait_sec <= 60:
        print(f"Waiting {wait_sec}s for next UTC minute bucket so baseline & incident are separated on time axis...")
        time.sleep(wait_sec)

    # 4. Inject official challenge incident and run challenge load test
    print("Injecting challenge incident and running challenge workload...")
    subprocess.run([sys.executable, "scripts/inject_incident.py"], cwd=REPO_ROOT, check=True)
    subprocess.run([sys.executable, "scripts/load_test.py", "--challenge", "--concurrency", "5"], cwd=REPO_ROOT, check=True)

    # Disable incident after challenge run so API is restored to healthy state
    subprocess.run([sys.executable, "scripts/inject_incident.py", "--scenario", challenge.incident, "--disable"], cwd=REPO_ROOT, check=True)

    # 5. Render dashboard and capture 12-incident-metric.png
    subprocess.run([sys.executable, "scripts/render_dashboard.py"], cwd=REPO_ROOT, check=True)
    render_html_file_png(
        EVIDENCE_DIR / "dashboard.html",
        EVIDENCE_DIR / "12-incident-metric.png",
        width=1520,
        height=860,
    )

    # 6. Find anomalous log records using exact CP4 8.2 commands and capture 13-incident-log.png
    raw_lines = [line for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [json.loads(l) for l in raw_lines]
    slow_rows = [
        r for r in rows
        if r.get("event") == "response_sent" and int(r.get("latency_ms") or 0) > challenge.latency_threshold_ms
    ]
    cmd13_1 = (
        "python -c \"import json; rows=[json.loads(l) for l in open('data/logs.jsonl', encoding='utf-8')]; "
        "[print(r['ts'], r['correlation_id'], r['feature'], r['latency_ms']) "
        "for r in rows if r.get('event')=='response_sent' and r.get('latency_ms',0)>2000]\""
    )
    out13_1 = "\n".join(f"{r['ts']} {r['correlation_id']} {r['feature']} {r['latency_ms']}" for r in slow_rows)

    target = slow_rows[0] if slow_rows else rows[-1]
    cid = target.get("correlation_id")
    cmd13_2 = (
        f"python -c \"import json; [print(json.dumps(json.loads(l), ensure_ascii=False, indent=2)) "
        f"for l in open('data/logs.jsonl', encoding='utf-8') if '{cid}' in l]\""
    )
    related = [json.loads(l) for l in raw_lines if cid in l]
    out13_2 = "\n".join(json.dumps(r, ensure_ascii=False, indent=2) for r in related)

    render_multi_cmd_png(
        f"13 - Incident Log ({challenge.challenge_id} | correlation_id = {cid})",
        [(cmd13_1, out13_1), (cmd13_2, out13_2)],
        EVIDENCE_DIR / "13-incident-log.png",
        width=1280,
        height=1180,
    )
    print(f"Captured 12-incident-metric.png and 13-incident-log.png for correlation_id={cid}")
    print("Slow rows:", out13_1)


if __name__ == "__main__":
    main()

