"""
Run this ONCE after deploying the webhook to Render:
    python create_assistant.py

It creates the Vapi assistant and prints the assistant ID.
Then assign a phone number to that assistant in the Vapi dashboard.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://voice-booking-agent.onrender.com
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def create_assistant():
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": "Nexus AI Booking Agent",
        "firstMessage": (
            "Hi there! You've reached Nexus AI Agency's scheduling assistant. "
            "I'm here to help you book a discovery call with our team. How can I help you today?"
        ),
        "endCallMessage": "Perfect, you're all booked! Looking forward to speaking with our team. Have a great day!",
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",  # Rachel — natural female voice
        },
        "model": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
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
                                "date": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format",
                                },
                                "duration_minutes": {
                                    "type": "integer",
                                    "description": "Slot duration in minutes (default 30)",
                                    "default": 30,
                                },
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
                                "name": {"type": "string", "description": "Caller's full name"},
                                "email": {"type": "string", "description": "Caller's email address"},
                                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                                "time": {"type": "string", "description": "Time in HH:MM AM/PM format, e.g. '10:00 AM'"},
                                "topic": {"type": "string", "description": "What they want to discuss"},
                            },
                            "required": ["name", "email", "date", "time"],
                        },
                    },
                },
            ],
        },
        "serverUrl": f"{WEBHOOK_URL}/vapi/webhook",
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
        },
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
    }

    resp = requests.post("https://api.vapi.ai/assistant", headers=headers, json=payload)

    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"\n✅ Assistant created successfully!")
        print(f"   ID: {data['id']}")
        print(f"\n📞 Next: Go to vapi.ai → Phone Numbers → Buy a number → assign assistant ID: {data['id']}")
        print(f"🌐 Or test via web at: https://vapi.ai/dashboard (Web Call button)")
        return data
    else:
        print(f"\n❌ Error {resp.status_code}: {resp.text}")
        return None


if __name__ == "__main__":
    if not VAPI_API_KEY:
        print("❌ VAPI_API_KEY not set in .env")
    elif not WEBHOOK_URL:
        print("❌ WEBHOOK_URL not set in .env — deploy to Render first")
    else:
        create_assistant()
