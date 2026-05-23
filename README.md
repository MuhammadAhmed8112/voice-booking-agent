---
title: Voice Booking Agent
emoji: 📞
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 📞 AI Voice Booking Agent

An AI voice agent that handles inbound calls, qualifies callers, checks real Google Calendar availability, and books discovery calls — fully automated.

## What It Does

1. **Answers calls** via a real phone number (powered by Vapi)
2. **Qualifies the caller** — collects name, email, and intent
3. **Checks live availability** — queries Google Calendar in real time
4. **Books the appointment** — creates a calendar event and emails an invite
5. **Confirms on the call** — reads back the booking details before hanging up

## Stack

| Layer | Tool |
|-------|------|
| Voice platform | [Vapi](https://vapi.ai) — 60 free minutes |
| LLM | Groq — Llama 3.3 70B (free) |
| Voice | ElevenLabs Rachel (via Vapi) |
| Calendar | Google Calendar API |
| Webhook | FastAPI on HuggingFace Spaces (free) |

## Setup

### 1. Clone & install
```bash
git clone https://github.com/MuhammadAhmed8112/voice-booking-agent
cd voice-booking-agent
pip install -r requirements.txt
cp .env.example .env
```

### 2. Google Calendar
- Enable [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
- Create a Service Account → download JSON key
- Share your calendar with the service account email
- Copy Calendar ID from Calendar settings

### 3. Deploy webhook (HuggingFace Spaces)
- Go to [huggingface.co](https://huggingface.co) → New Space → **Docker** SDK
- Name it `voice-booking-agent`
- Push this repo to the Space
- Add secrets in Space Settings (same env vars as above)
- Your webhook URL: `https://your-username-voice-booking-agent.hf.space`

### 4. Create Vapi assistant
```bash
# Set WEBHOOK_URL in .env first, then:
python create_assistant.py
```

### 5. Assign phone number
- Go to [vapi.ai](https://vapi.ai) → Phone Numbers → Buy → assign the assistant ID

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VAPI_API_KEY` | Vapi private key |
| `GROQ_API_KEY` | Groq API key |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON as a single-line string |
| `GOOGLE_CALENDAR_ID` | Target calendar ID |
| `WEBHOOK_URL` | Your Render deployment URL |
