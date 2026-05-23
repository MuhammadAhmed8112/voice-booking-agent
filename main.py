import json
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from calendar_service import check_availability, book_appointment

load_dotenv()

app = FastAPI(title="Voice Booking Agent — Webhook")


@app.get("/")
async def root():
    return {"status": "Voice Booking Agent webhook is live"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


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

            results = []
            for tool_call in tool_calls:
                if not tool_call:
                    continue

                fn = tool_call.get("function", {})
                fn_name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")

                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}

                print(f"Tool call: {fn_name} | Args: {args}")

                if fn_name == "check_availability":
                    result = check_availability(
                        date=args.get("date", ""),
                        duration_minutes=args.get("duration_minutes", 30),
                    )
                elif fn_name == "book_appointment":
                    result = book_appointment(
                        name=args.get("name", ""),
                        email=args.get("email", ""),
                        date=args.get("date", ""),
                        time=args.get("time", ""),
                        topic=args.get("topic", "Discovery Call"),
                    )
                else:
                    result = {"error": f"Unknown function: {fn_name}"}

                results.append({
                    "toolCallId": tool_call_id,
                    "result": json.dumps(result),
                })

            return JSONResponse({"results": results})

        # All other event types (status-update, end-of-call-report, etc.)
        return JSONResponse({"status": "ok"})

    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)
