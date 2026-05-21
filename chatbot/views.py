import base64
import hashlib
import hmac
import json
import logging

import requests as http_client
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bookings.models import User
from .llm_engine import process_booking_intent

logger = logging.getLogger(__name__)

_LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# Replace with your published LIFF URL once you have one.
_LIFF_LOGIN_URL = settings.LIFF_LOGIN_URL


# ── Signature verification ────────────────────────────────────────────────────

def _verify_signature(body: bytes, signature: str) -> bool:
    """Return True only when the X-Line-Signature header is valid."""
    secret = settings.LINE_CHANNEL_SECRET.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    # compare_digest prevents timing attacks.
    return hmac.compare_digest(expected, signature)


# ── LINE Messaging API helper ─────────────────────────────────────────────────

def _reply(reply_token: str, text: str) -> None:
    """Send a single text message back to the LINE user."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    try:
        resp = http_client.post(
            _LINE_REPLY_URL, json=payload, headers=headers, timeout=5
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send LINE reply (token=%.20s…)", reply_token)


# ── Booking service stub ──────────────────────────────────────────────────────

def create_booking_service(user: User, data: dict) -> dict:
    """
    STUB — wire up real booking logic here (Phase 4).

    Expected keys in data: room, date (YYYY-MM-DD), start_time (HH:MM),
    end_time (HH:MM).

    Returns {"success": bool, "message": str}.
    """
    logger.info(
        "create_booking_service called — user=%s, data=%s",
        user.username,
        data,
    )
    # TODO: combine date + start_time/end_time into aware DateTimeFields,
    #       resolve room_id, run conflict check, call Booking.objects.create().
    return {"success": True, "message": "mock booking accepted"}


# ── Event handler (pure logic, no HTTP concerns) ──────────────────────────────

def _handle_message_event(event: dict) -> None:
    """Process a single LINE text-message event end-to-end."""
    reply_token: str = event.get("replyToken", "")
    line_user_id: str = event.get("source", {}).get("userId", "")
    text: str = event.get("message", {}).get("text", "").strip()

    if not reply_token or not line_user_id or not text:
        return

    # ── Step 1: verify the LINE account is linked to a TU user ───────────────
    try:
        user = User.objects.get(line_user_id=line_user_id)
    except User.DoesNotExist:
        _reply(
            reply_token,
            f"กรุณาเข้าสู่ระบบเพื่อผูกบัญชีก่อนเริ่มใช้งานครับ:\n{_LIFF_LOGIN_URL}",
        )
        return

    # ── Step 2: run LLM intent extraction (multi-turn) ───────────────────────
    result = process_booking_intent(line_user_id, text)

    # ── Step 3: conversation still needs more information ────────────────────
    if not result.get("is_complete"):
        _reply(
            reply_token,
            result.get("reply_message") or "กรุณาลองใหม่อีกครั้งครับ",
        )
        return

    # ── Step 4: all slots collected — attempt to create the booking ──────────
    extracted = result.get("extracted_data", {})
    booking_result = create_booking_service(user, extracted)

    if booking_result["success"]:
        room = extracted.get("room") or "-"
        date = extracted.get("date") or "-"
        start = extracted.get("start_time") or "-"
        end = extracted.get("end_time") or "-"
        reply_text = (
            "จองห้องสำเร็จแล้วครับ!\n"
            f"ห้อง: {room}\n"
            f"วันที่: {date}\n"
            f"เวลา: {start} – {end}\n"
            "สถานะ: รออนุมัติ (ระบบจะแจ้งผลทาง LINE)"
        )
    else:
        reply_text = (
            f"ขออภัยครับ ไม่สามารถจองห้องได้\n"
            f"สาเหตุ: {booking_result.get('message', 'เกิดข้อผิดพลาด')}\n"
            "กรุณาเลือกช่วงเวลาอื่นหรือลองใหม่ครับ"
        )

    _reply(reply_token, reply_text)


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def line_webhook(request):
    """
    Receives POST requests from the LINE Platform.
    Verifies the signature, then dispatches each text-message event.
    """
    signature = request.META.get("HTTP_X_LINE_SIGNATURE", "")
    body = request.body

    if not _verify_signature(body, signature):
        logger.warning(
            "LINE webhook: invalid signature from %s",
            request.META.get("REMOTE_ADDR"),
        )
        return HttpResponse("Forbidden", status=403)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponse("Bad Request", status=400)

    for event in payload.get("events", []):
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            try:
                _handle_message_event(event)
            except Exception:
                # Log and continue — never let one bad event crash the whole delivery.
                logger.exception(
                    "Unhandled error processing LINE event: %s",
                    json.dumps(event)[:200],
                )

    # LINE expects 200 OK regardless of per-event errors.
    return HttpResponse("OK", status=200)
