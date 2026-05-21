import json
import logging

from google import genai
from google.genai import types
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_CACHE_TIMEOUT = 5 * 60  # 5 minutes
_CACHE_KEY_TEMPLATE = "chatbot:history:{}"

_SYSTEM_INSTRUCTION = (
    "You are a room booking assistant for Thammasat University. "
    "Extract room, date (YYYY-MM-DD), start_time (HH:MM), and end_time (HH:MM). "
    "If any information is missing, ask the user for it in polite Thai. "
    "You MUST return ONLY a JSON object with this exact schema: "
    '{"is_complete": boolean, "reply_message": "message to user", '
    '"extracted_data": {"room": null, "date": null, '
    '"start_time": null, "end_time": null}}'
)

_ERROR_RESPONSE = {
    "is_complete": False,
    "reply_message": "ขออภัยครับ เกิดข้อผิดพลาดในระบบ กรุณาลองใหม่อีกครั้ง",
    "extracted_data": {"room": None, "date": None, "start_time": None, "end_time": None},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_contents(history: list[dict]) -> list[types.Content]:
    """Convert cached history dicts to google-genai Content objects."""
    result = []
    for msg in history:
        parts = [types.Part(text=p) for p in msg.get("parts", [])]
        result.append(types.Content(role=msg["role"], parts=parts))
    return result


# ── Main function ─────────────────────────────────────────────────────────────

def process_booking_intent(line_user_id: str, current_message: str) -> dict:
    """
    Run one turn of the booking conversation through Gemini 2.0 Flash.

    Conversation history is stored in Django's cache keyed by line_user_id.
    Cleared when is_complete=true; refreshed with a 5-minute TTL otherwise.

    NOTE: Django's default LocMemCache is per-process. Use Redis/Memcached
    for multi-worker deployments.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    cache_key = _CACHE_KEY_TEMPLATE.format(line_user_id)
    history: list[dict] = cache.get(cache_key, [])

    # Append the new user turn before calling the model
    history.append({"role": "user", "parts": [current_message]})

    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.1,
    )

    try:
        response = client.models.generate_content(
            model="gemma-4-31b-it",
            config=config,
            contents=_to_contents(history),
        )
        raw_text = response.text
    except Exception:
        logger.exception("Gemini API call failed for LINE user %s", line_user_id)
        cache.set(cache_key, history, _CACHE_TIMEOUT)
        return _ERROR_RESPONSE

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error(
            "Gemini returned non-JSON for LINE user %s. Raw: %.200s",
            line_user_id,
            raw_text,
        )
        cache.set(cache_key, history, _CACHE_TIMEOUT)
        return _ERROR_RESPONSE

    # Append model reply to history for the next turn
    history.append({"role": "model", "parts": [raw_text]})

    if result.get("is_complete"):
        cache.delete(cache_key)
    else:
        cache.set(cache_key, history, _CACHE_TIMEOUT)

    return result
