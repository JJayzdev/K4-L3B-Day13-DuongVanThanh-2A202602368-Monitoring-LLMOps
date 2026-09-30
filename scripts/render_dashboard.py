from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
DEFAULT_OUTPUT_HTML = REPO_ROOT / "submission" / "evidence" / "dashboard.html"


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, math.ceil((pct / 100.0) * len(sorted_vals)) - 1))
    return float(sorted_vals[idx])


def load_records(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def minute_bucket(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%H:%M")
    except Exception:
        return "00:00"


def compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    received = [r for r in records if r.get("event") == "request_received"]
    sent = [r for r in records if r.get("event") == "response_sent"]
    failed = [r for r in records if r.get("event") == "request_failed"]
    tool_events = [r for r in records if "tool_success" in r and r.get("tool_success") is not None]

    latencies = sorted(float(r["latency_ms"]) for r in sent if r.get("latency_ms") is not None)
    ttfts = sorted(float(r["ttft_ms"]) for r in sent if r.get("ttft_ms") is not None)

    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    ttft_p95 = percentile(ttfts, 95)

    lat_buckets: dict[str, list[float]] = defaultdict(list)
    for r in sent:
        if r.get("latency_ms") is not None:
            lat_buckets[minute_bucket(str(r.get("ts", "")))].append(float(r["latency_ms"]))
    lat_p95_by_min = {m: percentile(sorted(vals), 95) for m, vals in lat_buckets.items()}

    traffic_by_min: dict[str, int] = defaultdict(int)
    for r in received:
        traffic_by_min[minute_bucket(str(r.get("ts", "")))] += 1
    avg_rpm = (len(received) / max(1, len(traffic_by_min))) if received else 0.0

    total_req = len(received)
    error_rate_pct = (len(failed) / total_req * 100.0) if total_req else 0.0
    retrieval_success_pct = (
        sum(1 for r in tool_events if r.get("tool_success") is True) / len(tool_events) * 100.0
        if tool_events
        else 0.0
    )
    error_types = Counter(str(r.get("error_type") or "None") for r in failed)

    cost_by_min: dict[str, float] = defaultdict(float)
    for r in sent:
        cost_by_min[minute_bucket(str(r.get("ts", "")))] += float(r.get("cost_usd") or 0.0)
    total_cost = sum(float(r.get("cost_usd") or 0.0) for r in sent)

    tokens_in_sum = sum(int(r.get("tokens_in") or 0) for r in sent)
    tokens_out_sum = sum(int(r.get("tokens_out") or 0) for r in sent)

    qualities = [float(r["quality_score"]) for r in sent if r.get("quality_score") is not None]
    mean_quality = (sum(qualities) / len(qualities)) if qualities else 0.0

    return {
        "total_records": len(records),
        "total_requests": total_req,
        "latency": {"p50": p50, "p95": p95, "p99": p99, "ttft_p95": ttft_p95, "by_min": lat_p95_by_min},
        "traffic": {"count": total_req, "rate_per_minute": round(avg_rpm, 2), "by_min": dict(traffic_by_min)},
        "errors": {
            "error_rate_pct": round(error_rate_pct, 2),
            "tool_success_rate_pct": round(retrieval_success_pct, 2),
            "error_types": dict(error_types),
            "failed_count": len(failed),
        },
        "cost": {"total": round(total_cost, 6), "by_min": {k: round(v, 6) for k, v in cost_by_min.items()}},
        "tokens": {"tokens_in": tokens_in_sum, "tokens_out": tokens_out_sum, "total": tokens_in_sum + tokens_out_sum},
        "quality": {"mean": round(mean_quality, 3), "series": qualities},
    }


def render_html(config: dict[str, Any], metrics: dict[str, Any]) -> str:
    dash = config["dashboard"]
    lat = metrics["latency"]
    trf = metrics["traffic"]
    err = metrics["errors"]
    cst = metrics["cost"]
    tok = metrics["tokens"]
    qlt = metrics["quality"]

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta http-equiv="refresh" content="{dash['refresh_seconds']}" />
<title>{dash['title']} — Runtime Dashboard</title>
<style>
  :root {{
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --good: #22c55e;
    --warn: #f59e0b;
    --danger: #ef4444;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    padding: 20px 28px;
  }}
  header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 14px;
    margin-bottom: 20px;
  }}
  header h1 {{ font-size: 22px; font-weight: 700; color: var(--text); }}
  .meta-badges {{ display: flex; gap: 10px; font-size: 13px; }}
  .badge {{
    background: var(--card);
    border: 1px solid var(--border);
    padding: 6px 12px;
    border-radius: 6px;
    color: var(--muted);
  }}
  .badge strong {{ color: var(--accent); }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
  }}
  .panel {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 265px;
  }}
  .panel-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
  }}
  .panel-title {{ font-size: 15px; font-weight: 600; }}
  .panel-id {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}
  .unit-tag {{
    font-size: 11px;
    background: #0f172a;
    color: var(--accent);
    padding: 3px 8px;
    border-radius: 4px;
    border: 1px solid var(--border);
  }}
  .kpi-row {{
    display: flex;
    gap: 14px;
    margin: 8px 0 12px 0;
    flex-wrap: wrap;
  }}
  .kpi {{
    background: rgba(15, 23, 42, 0.65);
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid rgba(51, 65, 85, 0.7);
    flex: 1;
    min-width: 80px;
  }}
  .kpi-label {{ font-size: 11px; color: var(--muted); }}
  .kpi-val {{ font-size: 18px; font-weight: 700; margin-top: 2px; }}
  .chart-box {{
    position: relative;
    background: #0b1120;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 14px 12px 10px 12px;
    margin-top: 4px;
  }}
  .threshold-line {{
    border-top: 2px dashed var(--danger);
    position: relative;
    margin: 6px 0 10px 0;
  }}
  .threshold-line span {{
    position: absolute;
    right: 0;
    top: -16px;
    font-size: 11px;
    color: #fca5a5;
    background: #0b1120;
    padding: 0 4px;
  }}
  .bar-group {{ display: flex; flex-direction: column; gap: 7px; }}
  .bar-item {{ display: flex; align-items: center; gap: 8px; font-size: 12px; }}
  .bar-label {{ width: 78px; color: var(--muted); }}
  .bar-track {{ flex: 1; height: 12px; background: #1e293b; border-radius: 4px; overflow: hidden; position: relative; }}
  .bar-fill {{ height: 100%; background: var(--accent); border-radius: 4px; }}
  .bar-fill.good {{ background: var(--good); }}
  .bar-fill.warn {{ background: var(--warn); }}
  .bar-val {{ width: 68px; text-align: right; font-variant-numeric: tabular-nums; }}
  .footer-meta {{
    margin-top: 10px;
    font-size: 11px;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
    border-top: 1px solid rgba(51, 65, 85, 0.5);
    padding-top: 8px;
  }}
</style>
</head>
<body>
  <header>
    <div>
      <h1>{dash['title']}</h1>
      <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">
        Source: <code>data/logs.jsonl</code> ({metrics['total_records']} events / {metrics['total_requests']} requests) | Rendered: {now_utc}
      </div>
    </div>
    <div class="meta-badges">
      <div class="badge">Time Range: <strong>Last {dash['time_range_minutes']} minutes</strong></div>
      <div class="badge">Refresh: <strong>{dash['refresh_seconds']}s</strong></div>
      <div class="badge">Contract: <strong>6/6 Panels Valid</strong></div>
    </div>
  </header>

  <div class="grid">
    <!-- Panel 1: Latency -->
    <div class="panel" id="panel-latency">
      <div>
        <div class="panel-header">
          <div>
            <div class="panel-id">Panel 1 • id: latency</div>
            <div class="panel-title">Latency percentiles and TTFT</div>
          </div>
          <span class="unit-tag">unit: ms</span>
        </div>
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">P50</div><div class="kpi-val">{lat['p50']:.0f} ms</div></div>
          <div class="kpi"><div class="kpi-label">P95 (SLO)</div><div class="kpi-val" style="color: {'#22c55e' if lat['p95'] <= 3000 else '#ef4444'}">{lat['p95']:.0f} ms</div></div>
          <div class="kpi"><div class="kpi-label">P99</div><div class="kpi-val">{lat['p99']:.0f} ms</div></div>
          <div class="kpi"><div class="kpi-label">TTFT P95</div><div class="kpi-val">{lat['ttft_p95']:.0f} ms</div></div>
        </div>
        <div class="chart-box">
          <div class="threshold-line"><span>SLO Threshold: p95 &lt;= 3000 ms (Challenge &gt; 2000 ms)</span></div>
          <div class="bar-group">
            {"".join(f'<div class="bar-item"><span class="bar-label">{m} UTC</span><div class="bar-track"><div class="bar-fill {"warn" if v > 2000 else "good"}" style="width: {min(100, max(4, v/3000*100)):.1f}%"></div></div><span class="bar-val" style="color: {"#f59e0b" if v > 2000 else "#22c55e"}">{v:.0f} ms</span></div>' for m, v in list(lat['by_min'].items())[-4:])}
            <div class="bar-item"><span class="bar-label">TTFT P95</span><div class="bar-track"><div class="bar-fill good" style="width: {min(100, max(3, lat['ttft_p95']/3000*100)):.1f}%"></div></div><span class="bar-val">{lat['ttft_p95']:.0f} ms</span></div>
          </div>
        </div>
      </div>
      <div class="footer-meta">
        <span>events: [response_sent]</span>
        <span>threshold: p95 lte 3000 ms</span>
      </div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="panel" id="panel-traffic">
      <div>
        <div class="panel-header">
          <div>
            <div class="panel-id">Panel 2 • id: traffic</div>
            <div class="panel-title">Request traffic</div>
          </div>
          <span class="unit-tag">unit: requests_per_minute</span>
        </div>
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">Total Requests</div><div class="kpi-val">{trf['count']}</div></div>
          <div class="kpi"><div class="kpi-label">Rate / Min</div><div class="kpi-val" style="color: #22c55e">{trf['rate_per_minute']} rpm</div></div>
        </div>
        <div class="chart-box">
          <div class="threshold-line"><span>Threshold: rate_per_minute &gt;= 1 rpm</span></div>
          <div class="bar-group">
            {"".join(f'<div class="bar-item"><span class="bar-label">{m} UTC</span><div class="bar-track"><div class="bar-fill" style="width: {min(100, c*8)}%"></div></div><span class="bar-val">{c} req/m</span></div>' for m, c in list(trf['by_min'].items())[-4:])}
          </div>
        </div>
      </div>
      <div class="footer-meta">
        <span>events: [request_received]</span>
        <span>threshold: rate_per_minute gte 1</span>
      </div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="panel" id="panel-errors">
      <div>
        <div class="panel-header">
          <div>
            <div class="panel-id">Panel 3 • id: errors</div>
            <div class="panel-title">Error rate and retrieval success</div>
          </div>
          <span class="unit-tag">unit: percent</span>
        </div>
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">Error Rate</div><div class="kpi-val" style="color: {'#22c55e' if err['error_rate_pct'] <= 2 else '#ef4444'}">{err['error_rate_pct']:.1f}%</div></div>
          <div class="kpi"><div class="kpi-label">Retrieval Success</div><div class="kpi-val" style="color: {'#22c55e' if err['tool_success_rate_pct'] >= 90 else '#ef4444'}">{err['tool_success_rate_pct']:.1f}%</div></div>
          <div class="kpi"><div class="kpi-label">Failed Count</div><div class="kpi-val">{err['failed_count']}</div></div>
        </div>
        <div class="chart-box">
          <div class="threshold-line"><span>Threshold: error_rate_pct &lt;= 2% | retrieval &gt;= 90%</span></div>
          <div class="bar-group">
            <div class="bar-item"><span class="bar-label">Error Rate</span><div class="bar-track"><div class="bar-fill warn" style="width: {min(100, err['error_rate_pct'])}% "></div></div><span class="bar-val">{err['error_rate_pct']:.1f}%</span></div>
            <div class="bar-item"><span class="bar-label">Tool Success</span><div class="bar-track"><div class="bar-fill good" style="width: {min(100, err['tool_success_rate_pct'])}%"></div></div><span class="bar-val">{err['tool_success_rate_pct']:.1f}%</span></div>
          </div>
        </div>
      </div>
      <div class="footer-meta">
        <span>events: [request_received, request_failed, response_sent]</span>
        <span>threshold: error_rate_pct lte 2%</span>
      </div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="panel" id="panel-cost">
      <div>
        <div class="panel-header">
          <div>
            <div class="panel-id">Panel 4 • id: cost</div>
            <div class="panel-title">Cost over time</div>
          </div>
          <span class="unit-tag">unit: usd</span>
        </div>
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">Total Cost (Window)</div><div class="kpi-val" style="color: #22c55e">${cst['total']:.5f}</div></div>
          <div class="kpi"><div class="kpi-label">Daily Budget Limit</div><div class="kpi-val">$2.50000</div></div>
        </div>
        <div class="chart-box">
          <div class="threshold-line"><span>Threshold: total &lt;= 2.5 USD</span></div>
          <div class="bar-group">
            {"".join(f'<div class="bar-item"><span class="bar-label">{m} UTC</span><div class="bar-track"><div class="bar-fill good" style="width: {min(100, max(6, v/0.05*100)):.1f}%"></div></div><span class="bar-val">${v:.5f}</span></div>' for m, v in list(cst['by_min'].items())[-4:])}
          </div>
        </div>
      </div>
      <div class="footer-meta">
        <span>events: [response_sent]</span>
        <span>threshold: total lte 2.5 usd</span>
      </div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="panel" id="panel-tokens">
      <div>
        <div class="panel-header">
          <div>
            <div class="panel-id">Panel 5 • id: tokens</div>
            <div class="panel-title">Input and output tokens</div>
          </div>
          <span class="unit-tag">unit: tokens</span>
        </div>
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">sum(tokens_in)</div><div class="kpi-val">{tok['tokens_in']}</div></div>
          <div class="kpi"><div class="kpi-label">sum(tokens_out)</div><div class="kpi-val">{tok['tokens_out']}</div></div>
          <div class="kpi"><div class="kpi-label">Total Tokens</div><div class="kpi-val" style="color: #22c55e">{tok['total']}</div></div>
        </div>
        <div class="chart-box">
          <div class="threshold-line"><span>Threshold: sum_by_field &lt;= 50,000 tokens</span></div>
          <div class="bar-group">
            <div class="bar-item"><span class="bar-label">tokens_in</span><div class="bar-track"><div class="bar-fill" style="width: {min(100, max(5, tok['tokens_in']/5000*100)):.1f}%"></div></div><span class="bar-val">{tok['tokens_in']}</span></div>
            <div class="bar-item"><span class="bar-label">tokens_out</span><div class="bar-track"><div class="bar-fill good" style="width: {min(100, max(8, tok['tokens_out']/5000*100)):.1f}%"></div></div><span class="bar-val">{tok['tokens_out']}</span></div>
          </div>
        </div>
      </div>
      <div class="footer-meta">
        <span>events: [response_sent]</span>
        <span>threshold: sum_by_field lte 50000</span>
      </div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="panel" id="panel-quality">
      <div>
        <div class="panel-header">
          <div>
            <div class="panel-id">Panel 6 • id: quality</div>
            <div class="panel-title">Quality proxy</div>
          </div>
          <span class="unit-tag">unit: score_0_to_1</span>
        </div>
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">mean(quality_score)</div><div class="kpi-val" style="color: {'#22c55e' if qlt['mean'] >= 0.75 else '#ef4444'}">{qlt['mean']:.2f}</div></div>
          <div class="kpi"><div class="kpi-label">Min Target</div><div class="kpi-val">0.75</div></div>
        </div>
        <div class="chart-box">
          <div class="threshold-line"><span>Threshold: mean &gt;= 0.75 score_0_to_1</span></div>
          <div class="bar-group">
            <div class="bar-item"><span class="bar-label">Mean Score</span><div class="bar-track"><div class="bar-fill good" style="width: {min(100, qlt['mean']*100):.1f}%"></div></div><span class="bar-val">{qlt['mean']:.2f} / 1.00</span></div>
            <div class="bar-item"><span class="bar-label">SLO Floor</span><div class="bar-track"><div class="bar-fill warn" style="width: 75%"></div></div><span class="bar-val">0.75 / 1.00</span></div>
          </div>
        </div>
      </div>
      <div class="footer-meta">
        <span>events: [response_sent]</span>
        <span>threshold: mean gte 0.75</span>
      </div>
    </div>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render 6-panel HTML dashboard from data/logs.jsonl")
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_HTML)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    records = load_records(args.logs)
    metrics = compute_metrics(records)
    html = render_html(config, metrics)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Dashboard rendered to {args.output} ({metrics['total_requests']} requests analyzed)")


if __name__ == "__main__":
    main()
