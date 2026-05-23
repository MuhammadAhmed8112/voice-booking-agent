import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from calendar_service import check_availability, book_appointment

load_dotenv()

app = FastAPI(title="Voice Booking Agent — Webhook")
executor = ThreadPoolExecutor(max_workers=4)


@app.get("/")
async def root():
    return {"status": "Voice Booking Agent webhook is live"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


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


@app.post("/livekit/actions")
async def livekit_actions(request: Request):
    """
    Handle LiveKit Action webhook calls.
    LiveKit sends:  POST {"name": "fn_name", "arguments": {...}}
    We respond:     {"output": "<string result for the LLM>"}
    """
    try:
        body = await request.json()
        print(f"LiveKit action received: {json.dumps(body)}")

        # Normalise across possible field-name variants LiveKit may use
        fn_name = (
            body.get("name")
            or body.get("function_name")
            or body.get("action")
            or ""
        )
        args = (
            body.get("arguments")
            or body.get("parameters")
            or body.get("args")
            or {}
        )
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        print(f"LiveKit tool: {fn_name} | args: {args}")

        try:
            result = await asyncio.wait_for(run_tool(fn_name, args), timeout=10.0)
        except asyncio.TimeoutError:
            result = {"error": "Tool timed out", "message": "Request took too long, please try again."}

        # Convert result dict → human-friendly string the LLM can read out
        if isinstance(result, dict):
            output = result.get("message") or json.dumps(result)
        else:
            output = str(result)

        return JSONResponse({"output": output, "result": result})

    except Exception as e:
        print(f"LiveKit action error: {e}")
        return JSONResponse({"output": f"Error: {e}", "error": str(e)}, status_code=200)


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    try:
        body = await request.json()
        message = body.get("message", {})
        msg_type = message.get("type", "")

        if msg_type == "tool-calls":
            # Support both Vapi webhook formats
            tool_calls = message.get("toolCalls", [])
            if not tool_calls:
                tool_calls = [
                    item.get("toolCall", {})
                    for item in message.get("toolWithToolCallList", [])
                ]

            # Run all tool calls concurrently
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

                print(f"Tool call: {fn_name} | Args: {args}")

                # 10-second timeout per tool call
                try:
                    result = await asyncio.wait_for(run_tool(fn_name, args), timeout=10.0)
                except asyncio.TimeoutError:
                    result = {"error": "Tool timed out", "message": "Request took too long, please try again."}

                return {"toolCallId": tool_call_id, "result": json.dumps(result)}

            tasks = [process_tool_call(tc) for tc in tool_calls]
            results = [r for r in await asyncio.gather(*tasks) if r is not None]

            return JSONResponse({"results": results})

        return JSONResponse({"status": "ok"})

    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)
