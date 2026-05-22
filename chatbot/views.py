import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta

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
    Create one or more Bookings from LLM-extracted data.

    Returns {"success": bool, "message": str, "booking": Booking|None, "booking_count": int, "conflict_count": int}.
    """
    # ── Base fields ───────────────────────────────────────────────────────────
    booking_type  = (data.get("booking_type") or "").strip()
    room_id       = (data.get("room") or "").strip()
    purpose_type  = (data.get("purpose_type") or "").strip()
    start_str     = (data.get("start_time") or "").strip()
    end_str       = (data.get("end_time") or "").strip()

    _fail = lambda msg: {"success": False, "message": msg, "booking": None, "booking_count": 0, "conflict_count": 0}

    if not all([booking_type, room_id, purpose_type, start_str, end_str]):
        return _fail("ข้อมูลพื้นฐานไม่ครบ (ห้อง / ประเภทการจอง / วัตถุประสงค์ / เวลา)")

    if booking_type not in ("single", "recurring"):
        return _fail("ประเภทการจองไม่ถูกต้อง")

    if purpose_type not in ("Teaching", "Training"):
        return _fail("วัตถุประสงค์ไม่ถูกต้อง")

    # ── Purpose-specific fields ───────────────────────────────────────────────
    purpose_kwargs: dict = {"purpose_type": purpose_type}
    if purpose_type == "Teaching":
        course_code = (data.get("course_code") or "").strip()
        course_name = (data.get("course_name") or "").strip()
        program     = (data.get("program") or "").strip()
        if not all([course_code, course_name, program]):
            return _fail("กรุณาระบุรหัสวิชา ชื่อวิชา และหลักสูตรให้ครบ")
        purpose_kwargs.update({"course_code": course_code, "course_name": course_name, "program": program})
    else:
        training_topic = (data.get("training_topic") or "").strip()
        if not training_topic:
            return _fail("กรุณาระบุชื่อเรื่องอบรม/ติว")
        purpose_kwargs["training_topic"] = training_topic

    # ── Resolve room ──────────────────────────────────────────────────────────
    try:
        room = Room.objects.get(room_id=room_id, is_active=True)
    except Room.DoesNotExist:
        return _fail(f"ไม่พบห้อง {room_id} หรือห้องปิดใช้งานอยู่")

    # ── Build list of target dates ────────────────────────────────────────────
    if booking_type == "single":
        date_str = (data.get("date") or "").strip()
        if not date_str:
            return _fail("กรุณาระบุวันที่")
        try:
            target_dates = [datetime.strptime(date_str, "%Y-%m-%d").date()]
        except ValueError:
            return _fail("รูปแบบวันที่ไม่ถูกต้อง")
    else:
        start_date_str = (data.get("start_date") or "").strip()
        end_date_str   = (data.get("end_date") or "").strip()
        days_of_week   = data.get("days_of_week")

        if not all([start_date_str, end_date_str, days_of_week is not None]):
            return _fail("กรุณาระบุวันที่เริ่ม วันที่สิ้นสุด และวันในสัปดาห์")
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date   = datetime.strptime(end_date_str,   "%Y-%m-%d").date()
        except ValueError:
            return _fail("รูปแบบวันที่ไม่ถูกต้อง")

        if start_date > end_date:
            return _fail("วันที่เริ่มต้องไม่เกินวันสิ้นสุด")

        target_dates = []
        cur = start_date
        while cur <= end_date:
            if cur.weekday() in days_of_week:
                target_dates.append(cur)
            cur += timedelta(days=1)

        if not target_dates:
            return _fail("ไม่พบวันที่ตรงเงื่อนไข กรุณาตรวจสอบช่วงวันที่และวันในสัปดาห์")

    # ── Create bookings ───────────────────────────────────────────────────────
    created: list[Booking] = []
    conflict_count = 0

    for target_date in target_dates:
        try:
            start_dt = timezone.make_aware(datetime.strptime(f"{target_date} {start_str}", "%Y-%m-%d %H:%M"))
            end_dt   = timezone.make_aware(datetime.strptime(f"{target_date} {end_str}",   "%Y-%m-%d %H:%M"))
        except ValueError:
            return _fail("รูปแบบเวลาไม่ถูกต้อง")

        if start_dt >= end_dt:
            return _fail("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")

        if start_dt <= timezone.now():
            if booking_type == "single":
                return _fail("ไม่สามารถจองห้องย้อนหลังได้ค่ะ กรุณาระบุวันและเวลาในอนาคต")
            conflict_count += 1
            continue

        conflict = Booking.objects.filter(
            room=room, status__in=["Pending", "Approved"],
            start_time__lt=end_dt, end_time__gt=start_dt,
        ).exists()

        if conflict:
            conflict_count += 1
            continue

        try:
            bk = Booking.objects.create(
                user=user, room=room, start_time=start_dt, end_time=end_dt,
                status="Pending", **purpose_kwargs,
            )
            created.append(bk)
            logger.info("Booking #%s created via LINE — user=%s room=%s", bk.id, user.username, room_id)
        except Exception:
            logger.exception("create_booking_service failed — user=%s data=%s", user.username, data)

    if not created:
        msg = (f"ห้อง {room.name} ถูกจองในช่วงเวลานั้นแล้ว กรุณาเลือกเวลาอื่น"
               if booking_type == "single"
               else "ไม่สามารถสร้างการจองได้เลย เนื่องจากทุกวันมีคิวชนหรือเวลาผ่านไปแล้ว")
        return _fail(msg)

    return {"success": True, "message": "จองสำเร็จ", "booking": created[0],
            "booking_count": len(created), "conflict_count": conflict_count}


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
        bk            = booking_result["booking"]
        booking_count = booking_result.get("booking_count", 1)
        conflict_skip = booking_result.get("conflict_count", 0)
        from django.utils.timezone import localtime
        start_fmt = localtime(bk.start_time).strftime("%d/%m/%Y %H:%M")
        end_fmt   = localtime(bk.end_time).strftime("%H:%M")

        if booking_count == 1:
            reply_text = (
                f"✅ ส่งคำขอจองห้องสำเร็จแล้วค่ะ!\n"
                f"ห้อง: {bk.room.room_id} – {bk.room.name}\n"
                f"วันที่: {start_fmt} – {end_fmt} น.\n"
                f"สถานะ: รออนุมัติจาก Admin\n"
                f"(เลขที่คำขอ: #{bk.id})"
            )
        else:
            skip_note = f"\n(ข้ามคิวชน {conflict_skip} วัน)" if conflict_skip else ""
            reply_text = (
                f"✅ ส่งคำขอจองห้องต่อเนื่องสำเร็จแล้วค่ะ!\n"
                f"ห้อง: {bk.room.room_id} – {bk.room.name}\n"
                f"เวลา: {start_fmt.split()[1]} – {end_fmt} น.\n"
                f"จำนวน: {booking_count} รายการ{skip_note}\n"
                f"สถานะ: รออนุมัติจาก Admin"
            )

        # ── Email notification to admins ──────────────────────────────────
        admin_emails = list(
            User.objects.filter(role="Admin")
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if admin_emails:
            display_name = user.first_name or user.username
            count_note = f"จำนวน {booking_count} รายการ " if booking_count > 1 else ""
            send_mail(
                subject=f"[แจ้งเตือน] คำขอจองห้องใหม่จาก LINE: {bk.room.room_id}",
                message=(
                    f"อาจารย์ {display_name} ได้ส่งคำขอจองห้องผ่าน LINE Bot\n\n"
                    f"ห้อง: {bk.room.room_id} – {bk.room.name}\n"
                    f"{count_note}เริ่ม: {start_fmt} – {end_fmt} น.\n\n"
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
