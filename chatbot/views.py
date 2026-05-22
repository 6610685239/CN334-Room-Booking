import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime

import requests as http_client
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bookings.models import Booking, Room, User
from .llm_engine import process_booking_intent

logger = logging.getLogger(__name__)

_LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
_LINE_PUSH_URL  = "https://api.line.me/v2/bot/message/push"

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


def push_line_message(line_user_id: str, text: str) -> None:
    """Send a push message to a LINE user (no reply token needed)."""
    if not line_user_id:
        return
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": line_user_id,
        "messages": [{"type": "text", "text": text}],
    }
    try:
        resp = http_client.post(
            _LINE_PUSH_URL, json=payload, headers=headers, timeout=5
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to push LINE message to %s", line_user_id)


# ── Booking service ───────────────────────────────────────────────────────────

def create_booking_service(user: User, data: dict) -> dict:
    """
    Create a Booking from LLM-extracted data.

    Expected keys in data:
        room       – room_id string e.g. "406-3"
        date       – "YYYY-MM-DD"
        start_time – "HH:MM"
        end_time   – "HH:MM"

    Returns {"success": bool, "message": str, "booking": Booking|None}.
    """
    room_id    = (data.get("room") or "").strip()
    date_str   = (data.get("date") or "").strip()
    start_str  = (data.get("start_time") or "").strip()
    end_str    = (data.get("end_time") or "").strip()

    if not all([room_id, date_str, start_str, end_str]):
        missing = [k for k, v in {"ห้อง": room_id, "วันที่": date_str,
                                   "เวลาเริ่ม": start_str, "เวลาสิ้นสุด": end_str}.items() if not v]
        return {"success": False, "message": f"ข้อมูลไม่ครบ: {', '.join(missing)}", "booking": None}

    # ── Resolve room ─────────────────────────────────────────────────────────
    try:
        room = Room.objects.get(room_id=room_id, is_active=True)
    except Room.DoesNotExist:
        return {"success": False, "message": f"ไม่พบห้อง {room_id} หรือห้องปิดใช้งานอยู่", "booking": None}

    # ── Parse to timezone-aware datetimes ────────────────────────────────────
    try:
        start_dt = timezone.make_aware(
            datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M")
        )
        end_dt = timezone.make_aware(
            datetime.strptime(f"{date_str} {end_str}", "%Y-%m-%d %H:%M")
        )
    except ValueError:
        return {"success": False, "message": "รูปแบบวันที่หรือเวลาไม่ถูกต้อง", "booking": None}

    if start_dt >= end_dt:
        return {"success": False, "message": "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น", "booking": None}

    if start_dt <= timezone.now():
        return {"success": False, "message": "ไม่สามารถจองห้องย้อนหลังได้ค่ะ กรุณาระบุวันและเวลาในอนาคต", "booking": None}

    # ── Conflict check ────────────────────────────────────────────────────────
    conflict = Booking.objects.filter(
        room=room,
        status__in=["Pending", "Approved"],
        start_time__lt=end_dt,
        end_time__gt=start_dt,
    ).exists()

    if conflict:
        return {"success": False, "message": f"ห้อง {room.name} ถูกจองในช่วงเวลานั้นแล้ว กรุณาเลือกเวลาอื่น", "booking": None}

    # ── Create booking ────────────────────────────────────────────────────────
    try:
        booking = Booking.objects.create(
            user=user,
            room=room,
            purpose_type="Training",
            training_topic="จองผ่าน LINE Bot (Roomasat)",
            start_time=start_dt,
            end_time=end_dt,
            status="Pending",
        )
        logger.info("Booking #%s created via LINE bot — user=%s room=%s", booking.id, user.username, room_id)
        return {"success": True, "message": "จองสำเร็จ", "booking": booking}
    except Exception:
        logger.exception("create_booking_service failed — user=%s data=%s", user.username, data)
        return {"success": False, "message": "เกิดข้อผิดพลาดในการบันทึกการจอง", "booking": None}


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
        bk = booking_result["booking"]
        from django.utils.timezone import localtime
        start_fmt = localtime(bk.start_time).strftime("%d/%m/%Y %H:%M")
        end_fmt   = localtime(bk.end_time).strftime("%H:%M")
        reply_text = (
            f"✅ ส่งคำขอจองห้องสำเร็จแล้วค่ะ!\n"
            f"ห้อง: {bk.room.room_id} – {bk.room.name}\n"
            f"วันที่: {start_fmt} – {end_fmt} น.\n"
            f"สถานะ: รออนุมัติจาก Admin\n"
            f"(เลขที่คำขอ: #{bk.id})"
        )

        # ── Email notification to admins ──────────────────────────────────
        admin_emails = list(
            User.objects.filter(role="Admin")
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if admin_emails:
            display_name = user.first_name or user.username
            send_mail(
                subject=f"[แจ้งเตือน] คำขอจองห้องใหม่จาก LINE: {bk.room.room_id}",
                message=(
                    f"อาจารย์ {display_name} ได้ส่งคำขอจองห้องผ่าน LINE Bot\n\n"
                    f"ห้อง: {bk.room.room_id} – {bk.room.name}\n"
                    f"วันที่: {start_fmt} – {end_fmt} น.\n"
                    f"เลขที่คำขอ: #{bk.id}\n\n"
                    f"กรุณาตรวจสอบและอนุมัติที่หน้า Dashboard"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
    else:
        reply_text = (
            f"❌ ไม่สามารถจองห้องได้ค่ะ\n"
            f"สาเหตุ: {booking_result.get('message', 'เกิดข้อผิดพลาด')}\n"
            "กรุณาลองใหม่หรือเลือกช่วงเวลาอื่นค่ะ"
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
