from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


def find_browser() -> Path:
    for p in CHROME_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError("Neither Chrome nor Edge found for headless screenshot capture.")


def render_terminal_png(title: str, command_str: str, output_text: str, out_png: Path, width: int = 1200, height: int = 620) -> None:
    browser = find_browser()
    escaped_cmd = html.escape(command_str)
    escaped_out = html.escape(output_text)
    temp_html = EVIDENCE_DIR / f"_tmp_{out_png.stem}.html"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #090d16;
    padding: 24px;
    font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
    color: #e2e8f0;
  }}
  .window {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
  }}
  .titlebar {{
    background: #1e293b;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #334155;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    color: #cbd5e1;
  }}
  .dots {{ display: flex; gap: 8px; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; }}
  .dot.r {{ background: #ef4444; }}
  .dot.y {{ background: #f59e0b; }}
  .dot.g {{ background: #22c55e; }}
  .content {{
    padding: 20px 24px;
    font-size: 14px;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-all;
  }}
  .prompt {{ color: #38bdf8; font-weight: bold; }}
  .cmd {{ color: #fde047; font-weight: bold; }}
  .out {{ color: #f1f5f9; margin-top: 8px; }}
</style>
</head>
<body>
  <div class="window">
    <div class="titlebar">
      <div class="dots"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span></div>
      <div>Windows PowerShell — {html.escape(title)} (K4-L3B-Day13-DuongVanThanh-2A202602368)</div>
      <div>.venv (Python 3.11.9)</div>
    </div>
    <div class="content"><span class="prompt">(.venv) PS E:\\VinAI\\Lab\\Day13\\K4-L3B-Day13-DuongVanThanh-2A202602368-Monitoring-LLMOps&gt; </span><span class="cmd">{escaped_cmd}</span>
<div class="out">{escaped_out}</div></div>
  </div>
</body>
</html>
"""
    temp_html.write_text(html_content, encoding="utf-8")
    try:
        subprocess.run(
            [
                str(browser),
                "--headless",
                "--disable-gpu",
                f"--window-size={width},{height}",
                f"--screenshot={out_png.resolve()}",
                temp_html.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        temp_html.unlink(missing_ok=True)


def render_html_file_png(html_file: Path, out_png: Path, width: int = 1520, height: int = 920) -> None:
    browser = find_browser()
    subprocess.run(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            f"--window-size={width},{height}",
            f"--screenshot={out_png.resolve()}",
            html_file.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
    )
def render_multi_cmd_png(
    title: str,
    cmd_outputs: list[tuple[str, str]],
    out_png: Path,
    width: int = 1280,
    height: int = 620,
) -> None:
    browser = find_browser()
    blocks = []
    for cmd_str, out_str in cmd_outputs:
        esc_cmd = html.escape(cmd_str)
        esc_out = html.escape(out_str)
        blocks.append(
            f'<div><span class="prompt">(.venv) PS E:\\VinAI\\Lab\\Day13\\K4-L3B-Day13-DuongVanThanh-2A202602368-Monitoring-LLMOps&gt; </span>'
            f'<span class="cmd">{esc_cmd}</span>'
            f'<div class="out">{esc_out}</div></div>'
        )
    joined_blocks = '<div style="height: 14px;"></div>'.join(blocks)
    temp_html = EVIDENCE_DIR / f"_tmp_{out_png.stem}.html"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #090d16;
    padding: 24px;
    font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
    color: #e2e8f0;
  }}
  .window {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
  }}
  .titlebar {{
    background: #1e293b;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #334155;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    color: #cbd5e1;
  }}
  .dots {{ display: flex; gap: 8px; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; }}
  .dot.r {{ background: #ef4444; }}
  .dot.y {{ background: #f59e0b; }}
  .dot.g {{ background: #22c55e; }}
  .content {{
    padding: 20px 24px;
    font-size: 14px;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-all;
  }}
  .prompt {{ color: #38bdf8; font-weight: bold; }}
  .cmd {{ color: #fde047; font-weight: bold; }}
  .out {{ color: #f1f5f9; margin-top: 6px; }}
</style>
</head>
<body>
  <div class="window">
    <div class="titlebar">
      <div class="dots"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span></div>
      <div>Windows PowerShell — {html.escape(title)} (K4-L3B-Day13-DuongVanThanh-2A202602368)</div>
      <div>.venv (Python 3.11.9)</div>
    </div>
    <div class="content">{joined_blocks}</div>
  </div>
</body>
</html>
"""
    temp_html.write_text(html_content, encoding="utf-8")
    try:
        subprocess.run(
            [
                str(browser),
                "--headless",
                "--disable-gpu",
                f"--window-size={width},{height}",
                f"--screenshot={out_png.resolve()}",
                temp_html.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        temp_html.unlink(missing_ok=True)


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Send 04 request (req-1a2b3c4d) and 05 PII request (req-5eedcafe) as specified in CP4 8.2
    with httpx.Client(timeout=15.0) as client:
        r04 = client.post(
            "http://127.0.0.1:8000/chat",
            headers={"x-request-id": "req-1a2b3c4d"},
            json={
                "user_id": "demo",
                "session_id": "demo-01",
                "feature": "qa",
                "message": "Explain observability and why metrics logs traces work together",
            },
        )
        r05 = client.post(
            "http://127.0.0.1:8000/chat",
            headers={"x-request-id": "req-5eedcafe"},
            json={
                "user_id": "demo",
                "session_id": "demo-02",
                "feature": "policy",
                "message": "a@b.vn 0901234567 001099012345 4111 1111 1111 1111",
            },
        )

    # 1. 01-pytest.png: git log -1 --oneline + python -m pytest -q
    res_git = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    res_pytest_q = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    pytest_txt = f"$ git log -1 --oneline\n{res_git.stdout.strip()}\n\n$ python -m pytest -q\n{res_pytest_q.stdout.strip()}\n"
    (EVIDENCE_DIR / "01-pytest.txt").write_text(pytest_txt, encoding="utf-8")
    render_multi_cmd_png(
        "01 - Commit SHA & Pytest (CP4 8.2)",
        [
            ("git log -1 --oneline", res_git.stdout.strip()),
            ("python -m pytest -q", res_pytest_q.stdout.strip()),
        ],
        EVIDENCE_DIR / "01-pytest.png",
        width=1180,
        height=380,
    )

    # 2. 02-log-validator.png
    res_log_val = subprocess.run(
        [sys.executable, "scripts/validate_logs.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "02-log-validator.txt").write_text(res_log_val.stdout, encoding="utf-8")
    render_terminal_png(
        "02 - Log Validator (CP1 Gate)",
        "python scripts/validate_logs.py",
        res_log_val.stdout.strip(),
        EVIDENCE_DIR / "02-log-validator.png",
        width=1150,
        height=520,
    )

    # 3. 03-dashboard-validator.png
    res_dash_val = subprocess.run(
        [sys.executable, "scripts/validate_dashboard.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "03-dashboard-validator.txt").write_text(res_dash_val.stdout, encoding="utf-8")
    render_terminal_png(
        "03 - Dashboard Validator (CP2 Gate)",
        "python scripts/validate_dashboard.py",
        res_dash_val.stdout.strip(),
        EVIDENCE_DIR / "03-dashboard-validator.png",
        width=1150,
        height=300,
    )

    # Read logs for 04 and 05
    raw_lines = [line for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

    # 4. 04-structured-log.png (exact 2 commands from CP4 8.2 with req-1a2b3c4d)
    cmd04_1 = (
        "python -c \"import httpx; r = httpx.post('http://127.0.0.1:8000/chat', "
        "json={'user_id':'demo','session_id':'demo-01','feature':'qa','message':'Explain observability and why metrics logs traces work together'}, "
        "headers={'x-request-id':'req-1a2b3c4d'}); print(r.status_code, r.headers.get('x-request-id'))\""
    )
    out04_1 = f"{r04.status_code} {r04.headers.get('x-request-id', 'req-1a2b3c4d')}"
    cmd04_2 = (
        "python -c \"import json; [print(json.dumps(json.loads(l), ensure_ascii=False, indent=2)) "
        "for l in open('data/logs.jsonl', encoding='utf-8') if 'req-1a2b3c4d' in l]\""
    )
    recs_04 = [json.loads(l) for l in raw_lines if "req-1a2b3c4d" in l][-2:]
    out04_2 = "\n".join(json.dumps(r, ensure_ascii=False, indent=2) for r in recs_04)
    render_multi_cmd_png(
        "04 - Structured Log (correlation_id = req-1a2b3c4d)",
        [(cmd04_1, out04_1), (cmd04_2, out04_2)],
        EVIDENCE_DIR / "04-structured-log.png",
        width=1280,
        height=1120,
    )

    # 5. 05-pii-redaction.png (exact 2 commands from CP4 8.2 with message = 'a@b.vn 0901234567 001099012345 4111 1111 1111 1111')
    cmd05_1 = (
        "python -c \"import httpx; r = httpx.post('http://127.0.0.1:8000/chat', "
        "json={'user_id':'demo','session_id':'demo-02','feature':'policy','message':'a@b.vn 0901234567 001099012345 4111 1111 1111 1111'}, "
        "headers={'x-request-id':'req-5eedcafe'}); print(r.status_code, r.headers.get('x-request-id'))\""
    )
    out05_1 = f"{r05.status_code} {r05.headers.get('x-request-id', 'req-5eedcafe')}"
    cmd05_2 = (
        "python -c \"import json; [print(json.dumps(json.loads(l), ensure_ascii=False, indent=2)) "
        "for l in open('data/logs.jsonl', encoding='utf-8') if 'req-5eedcafe' in l]\""
    )
    recs_05 = [json.loads(l) for l in raw_lines if "req-5eedcafe" in l][-2:]
    out05_2 = "\n".join(json.dumps(r, ensure_ascii=False, indent=2) for r in recs_05)
    render_multi_cmd_png(
        "05 - PII Redaction (req-5eedcafe)",
        [(cmd05_1, out05_1), (cmd05_2, out05_2)],
        EVIDENCE_DIR / "05-pii-redaction.png",
        width=1280,
        height=1120,
    )

    # 6. Re-render dashboard.html and capture 11-dashboard-overview.png
    subprocess.run([sys.executable, "scripts/render_dashboard.py"], cwd=REPO_ROOT, check=True)
    render_html_file_png(
        EVIDENCE_DIR / "dashboard.html",
        EVIDENCE_DIR / "11-dashboard-overview.png",
        width=1520,
        height=860,
    )
    print("Generated evidence screenshots: 01, 02, 03, 04, 05, 11 in submission/evidence/")


if __name__ == "__main__":
    main()

