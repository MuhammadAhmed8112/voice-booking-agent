import json
import os
import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from dotenv import load_dotenv
from calendar_service import check_availability, book_appointment

load_dotenv()

app = FastAPI(title="Voice Booking Agent — Webhook")
executor = ThreadPoolExecutor(max_workers=4)

# ── In-memory call tracker (last 100 tool invocations) ───────────────────────
_call_log: deque = deque(maxlen=100)


def _record(tool: str, args: dict, result: dict, duration_ms: float, source: str = "livekit"):
    """Append one tool-call record to the in-memory log."""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": source,
        "tool": tool,
        "args": args,
        "result": result,
        "duration_ms": round(duration_ms, 1),
        "status": "error" if "error" in result else "ok",
    }
    _call_log.appendleft(entry)
    # Also print so it shows up in HuggingFace Space logs
    print(
        f"[{entry['ts']}] [{source}] {tool} "
        f"| args={json.dumps(args)} "
        f"| status={entry['status']} "
        f"| {duration_ms:.0f}ms"
    )


# ── Utility ───────────────────────────────────────────────────────────────────

async def run_tool(fn_name: str, args: dict) -> dict:
    """Run calendar tools in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()

    if fn_name == "check_availability":
        return await loop.run_in_executor(
            executor,
            lambda: check_availability(
                date=args.get("date", ""),
                duration_minutes=args.get("duration_minutes", 30),
            ),
        )
    elif fn_name == "book_appointment":
        return await loop.run_in_executor(
            executor,
            lambda: book_appointment(
                name=args.get("name", ""),
                email=args.get("email", ""),
                date=args.get("date", ""),
                time=args.get("time", ""),
                topic=args.get("topic", "Discovery Call"),
            ),
        )
    else:
        return {"error": f"Unknown function: {fn_name}"}


def _format_output(result: dict) -> str:
    """Convert a result dict to a human-readable string the LLM can speak."""
    if isinstance(result, dict):
        return result.get("message") or json.dumps(result)
    return str(result)


async def _timed_tool(fn_name: str, args: dict, source: str) -> tuple[dict, float]:
    """Run a tool, enforce 10 s timeout, return (result, duration_ms)."""
    t0 = time.perf_counter()
    try:
        result = await asyncio.wait_for(run_tool(fn_name, args), timeout=10.0)
    except asyncio.TimeoutError:
        result = {"error": "timeout", "message": "Request took too long, please try again."}
    duration_ms = (time.perf_counter() - t0) * 1000
    _record(fn_name, args, result, duration_ms, source=source)
    return result, duration_ms


# ── Standard endpoints ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "Voice Booking Agent webhook is live"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ── Call log viewer ───────────────────────────────────────────────────────────

@app.get("/logs", response_class=HTMLResponse)
async def view_logs():
    """
    Browser-friendly live call log.
    Visit https://md8112-voice-booking-agent.hf.space/logs
    The page auto-refreshes every 5 seconds.
    """
    rows = ""
    for e in _call_log:
        status_color = "#4caf50" if e["status"] == "ok" else "#f44336"
        args_str = json.dumps(e["args"], indent=2)
        result_str = json.dumps(e["result"], indent=2)
        rows += f"""
        <tr>
          <td>{e['ts']}</td>
          <td><span style="color:#90caf9">{e['source']}</span></td>
          <td><strong>{e['tool']}</strong></td>
          <td><pre>{args_str}</pre></td>
          <td><pre>{result_str}</pre></td>
          <td style="color:{status_color}">{e['status']}</td>
          <td>{e['duration_ms']} ms</td>
        </tr>"""

    if not rows:
        rows = "<tr><td colspan='7' style='text-align:center;color:#888'>No tool calls yet — start a call!</td></tr>"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="5">
  <title>Voice Agent — Call Log</title>
  <style>
    body {{ background:#121212; color:#e0e0e0; font-family:monospace; padding:20px; }}
    h1 {{ color:#90caf9; }}
    .badge {{ background:#1e1e1e; border:1px solid #333; padding:4px 10px;
              border-radius:4px; font-size:12px; color:#aaa; }}
    table {{ width:100%; border-collapse:collapse; margin-top:16px; font-size:13px; }}
    th {{ background:#1e1e1e; color:#90caf9; padding:8px 12px; text-align:left;
          border-bottom:1px solid #333; }}
    td {{ padding:8px 12px; border-bottom:1px solid #222; vertical-align:top; }}
    tr:hover td {{ background:#1a1a2e; }}
    pre {{ margin:0; white-space:pre-wrap; word-break:break-all; max-width:320px;
           color:#ce93d8; }}
    .refresh {{ float:right; color:#666; font-size:12px; }}
  </style>
</head>
<body>
  <h1>Voice Agent — Live Call Log</h1>
  <span class="badge">Auto-refreshes every 5 s</span>
  <span class="refresh">Showing last {len(_call_log)} of 100 events</span>
  <table>
    <thead>
      <tr>
        <th>Timestamp (UTC)</th>
        <th>Source</th>
        <th>Tool</th>
        <th>Arguments</th>
        <th>Result</th>
        <th>Status</th>
        <th>Latency</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/logs/json")
async def logs_json():
    """Raw JSON version of the call log — useful for programmatic access."""
    return JSONResponse(list(_call_log))


# ── LiveKit HTTP tools ────────────────────────────────────────────────────────

@app.post("/livekit/check_availability")
async def livekit_check_availability(request: Request):
    try:
        args = await request.json()
        result, _ = await _timed_tool("check_availability", args, source="livekit")
        return JSONResponse({"output": _format_output(result), "result": result})
    except Exception as e:
        _record("check_availability", {}, {"error": str(e)}, 0, source="livekit")
        return JSONResponse({"output": f"Error: {e}"}, status_code=200)


@app.post("/livekit/book_appointment")
async def livekit_book_appointment(request: Request):
    try:
        args = await request.json()
        result, _ = await _timed_tool("book_appointment", args, source="livekit")
        return JSONResponse({"output": _format_output(result), "result": result})
    except Exception as e:
        _record("book_appointment", {}, {"error": str(e)}, 0, source="livekit")
        return JSONResponse({"output": f"Error: {e}"}, status_code=200)


# ── Vapi webhook (kept for backwards compatibility) ───────────────────────────

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    try:
        body = await request.json()
        message = body.get("message", {})
        msg_type = message.get("type", "")

        if msg_type == "tool-calls":
            tool_calls = message.get("toolCalls", [])
            if not tool_calls:
                tool_calls = [
                    item.get("toolCall", {})
                    for item in message.get("toolWithToolCallList", [])
                ]

            async def process_tool_call(tool_call):
                if not tool_call:
                    return None
                fn = tool_call.get("function", {})
                fn_name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")

                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}

                result, _ = await _timed_tool(fn_name, args, source="vapi")
                return {"toolCallId": tool_call_id, "result": json.dumps(result)}

            tasks = [process_tool_call(tc) for tc in tool_calls]
            results = [r for r in await asyncio.gather(*tasks) if r is not None]
            return JSONResponse({"results": results})

        return JSONResponse({"status": "ok"})

    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)
