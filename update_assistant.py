"""
Updates the existing Vapi assistant with better endpointing and a faster model.
Run: python update_assistant.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
ASSISTANT_ID = "9fd5ddae-13c9-4b5b-aa84-6be0cccb5a01"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")


def update_assistant():
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    patch = {
        # ── Faster model ─────────────────────────────────────────────────────
        "model": {
            "provider": "groq",
            "model": "llama-3.1-8b-instant",   # fastest Groq model with tool use support
            "temperature": 0.3,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Alex, a professional AI scheduling assistant for Nexus AI Agency — "
                        "a B2B AI automation agency that builds chatbots, voice agents, and workflow automations.\n\n"
                        "YOUR JOB: Help callers book a 30-minute discovery call with our team.\n\n"
                        "FLOW:\n"
                        "1. Greet warmly and confirm they want to book a call\n"
                        "2. Collect: full name, email address, what they want to discuss\n"
                        "3. Ask for their preferred date (e.g. 'this Thursday' or 'May 28th')\n"
                        "4. Call check_availability with that date in YYYY-MM-DD format\n"
                        "5. Offer up to 3 available time slots naturally\n"
                        "6. Once they choose, call book_appointment to confirm\n"
                        "7. Read out the confirmation and wish them well\n\n"
                        "RULES:\n"
                        "- Keep responses under 3 sentences\n"
                        "- Never read IDs, URLs, or raw JSON\n"
                        "- If asked about pricing/services, say 'Our team will cover everything on the call'\n"
                        "- Always confirm the booking out loud before ending"
                    ),
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "check_availability",
                        "description": "Check available 30-minute slots on a given date (business hours 9 AM–5 PM UTC).",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                                "duration_minutes": {"type": "integer", "default": 30},
                            },
                            "required": ["date"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "book_appointment",
                        "description": "Book a discovery call and send a calendar invite to the caller.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "date": {"type": "string", "description": "YYYY-MM-DD"},
                                "time": {"type": "string", "description": "e.g. '10:00 AM'"},
                                "topic": {"type": "string"},
                            },
                            "required": ["name", "email", "date", "time"],
                        },
                    },
                },
            ],
        },

        # ── Endpointing — wait for the user to finish speaking ────────────────
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
            "endpointing": 500,          # max allowed — wait 500ms of silence before processing
        },

        # ── Turn-taking — don't interrupt mid-sentence ────────────────────────
        "startSpeakingPlan": {
            "waitSeconds": 1.2,          # wait 1.2s after user stops before replying
            "smartEndpointingEnabled": True,
            "transcriptionEndpointingPlan": {
                "onPunctuationSeconds": 0.6,    # after . ? ! wait 0.6s
                "onNoPunctuationSeconds": 1.8,  # no punctuation → wait 1.8s
                "onNumberSeconds": 0.6,
            },
        },

        "stopSpeakingPlan": {
            "numWords": 3,           # only interrupt agent after user says 3+ words
            "voiceSeconds": 0.4,     # require 0.4s of sustained voice
            "backoffSeconds": 1.5,   # after agent is interrupted, wait 1.5s before speaking
        },
    }

    resp = requests.patch(
        f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
        headers=headers,
        json=patch,
    )

    if resp.status_code in (200, 201):
        print("Assistant updated successfully!")
        print(f"Model: llama3-groq-8b-8192-tool-use")
        print(f"Endpointing: 600ms | Wait before reply: 1.2s")
    else:
        print(f"Error {resp.status_code}: {resp.text}")


if __name__ == "__main__":
    update_assistant()
