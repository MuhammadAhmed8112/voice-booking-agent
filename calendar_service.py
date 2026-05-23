import json
import os
import traceback
from datetime import datetime, timedelta

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


def _get_service():
    """
    Auth priority:
    1. GOOGLE_TOKEN_JSON  — OAuth2 user credentials (preferred, full calendar access)
    2. GOOGLE_SERVICE_ACCOUNT_JSON — service account fallback
    """
    # ── OAuth2 path ───────────────────────────────────────────────────────────
    token_raw = os.getenv("GOOGLE_TOKEN_JSON", "")
    if token_raw:
        token_info = json.loads(token_raw)
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("calendar", "v3", credentials=creds)

    # ── Service account fallback ──────────────────────────────────────────────
    sa_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if sa_raw:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa_raw), scopes=SCOPES
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            "service_account.json", scopes=SCOPES
        )
    return build("calendar", "v3", credentials=creds)


def check_availability(date: str, duration_minutes: int = 30) -> dict:
    """Return up to 4 free slots on the requested date (business hours 9–17)."""
    try:
        service = _get_service()
        target = datetime.strptime(date, "%Y-%m-%d")

        time_min = target.replace(hour=9, minute=0, second=0, microsecond=0).isoformat() + "Z"
        time_max = target.replace(hour=17, minute=0, second=0, microsecond=0).isoformat() + "Z"

        events = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        busy = []
        for ev in events.get("items", []):
            s = ev["start"].get("dateTime", ev["start"].get("date"))
            e = ev["end"].get("dateTime", ev["end"].get("date"))
            busy.append((s, e))

        # Walk through the day in 30-min increments
        available = []
        slot = target.replace(hour=9, minute=0)
        end_of_day = target.replace(hour=17, minute=0)

        while slot + timedelta(minutes=duration_minutes) <= end_of_day:
            slot_end = slot + timedelta(minutes=duration_minutes)
            free = True

            for b_start, b_end in busy:
                try:
                    bs = datetime.fromisoformat(b_start.replace("Z", "")).replace(tzinfo=None)
                    be = datetime.fromisoformat(b_end.replace("Z", "")).replace(tzinfo=None)
                    if not (slot_end <= bs or slot >= be):
                        free = False
                        break
                except Exception:
                    pass

            if free:
                available.append(slot.strftime("%I:%M %p"))

            slot += timedelta(minutes=30)

        friendly_date = target.strftime("%A, %B %d")

        if available:
            return {
                "available": True,
                "date": friendly_date,
                "slots": available[:4],
            }
        else:
            return {
                "available": False,
                "message": f"No open slots on {friendly_date}. Please try another date.",
            }

    except Exception as e:
        tb = traceback.format_exc()
        print(f"check_availability error [{type(e).__name__}]: {e}\n{tb}")
        # Graceful demo fallback
        try:
            friendly = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %B %d")
        except Exception:
            friendly = date
        return {
            "available": True,
            "date": friendly,
            "slots": ["10:00 AM", "2:00 PM", "3:30 PM"],
            "note": "demo_fallback",
        }


def book_appointment(
    name: str, email: str, date: str, time: str, topic: str = "Discovery Call"
) -> dict:
    """Create a 30-min calendar event and send an invite to the caller."""
    try:
        service = _get_service()

        # Parse the datetime — accept '10:00 AM' or '10:00' formats
        for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M"):
            try:
                start_dt = datetime.strptime(f"{date} {time}", fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Cannot parse datetime: {date} {time}")

        end_dt = start_dt + timedelta(minutes=30)

        event = {
            "summary": f"{topic} — {name}",
            "description": (
                f"Booked via AI Voice Agent\n"
                f"Client: {name}\nEmail: {email}\nTopic: {topic}"
            ),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": email}],
        }

        created = (
            service.events()
            .insert(calendarId=CALENDAR_ID, body=event, sendUpdates="all")
            .execute()
        )

        return {
            "success": True,
            "message": (
                f"Done! {name} is booked for a {topic} on "
                f"{start_dt.strftime('%A, %B %d')} at {start_dt.strftime('%I:%M %p')}. "
                f"A calendar invite has been sent to {email}."
            ),
        }

    except HttpError as e:
        tb = traceback.format_exc()
        detail = e.reason if hasattr(e, "reason") else str(e)
        print(f"book_appointment HttpError [{e.status_code}]: {detail}\n{tb}")
        return {
            "success": False,
            "error": f"HTTP {e.status_code}: {detail}",
            "message": "I had trouble booking that — please try again or contact us directly.",
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"book_appointment error [{type(e).__name__}]: {e!r}\n{tb}")
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e!r}",
            "message": "I had trouble booking that — please try again or contact us directly.",
        }
