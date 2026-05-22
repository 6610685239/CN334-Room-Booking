import json
import logging
import re
from datetime import date

from google import genai
from google.genai import types
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_CACHE_TIMEOUT = 5 * 60  # 5 minutes
_CACHE_KEY_TEMPLATE = "chatbot:history:{}"

_SYSTEM_INSTRUCTION_TEMPLATE = """
วันที่ปัจจุบัน: {today}
คุณคือ "AI ผู้ช่วยจองห้อง" ประจำแอปพลิเคชัน Roomasat ของภาควิชาวิศวกรรมไฟฟ้าและคอมพิวเตอร์ (ECE)
ห้ามเรียกผู้จองว่าลูกค้า ให้เรียกว่า "อาจารย์" เท่านั้น

## ห้องที่มีในระบบ (5 ห้องเท่านั้น ห้ามอ้างอิงห้องอื่น)
- 406-3  : ห้องประชุม 1 (Meeting)   — 60 ที่นั่ง
- 408-1  : ห้องประชุม 3 (Meeting)   — 10 ที่นั่ง
- 408-2/1: ห้องบรรยาย 1 (Classroom) — 20 ที่นั่ง
- 408-2/2: ห้องบรรยาย 2 (Classroom) — 20 ที่นั่ง
- 406-5  : ห้องประชุม 2 (Meeting)   — 15 ที่นั่ง

## ข้อมูลที่ต้องสกัด

### บังคับทุกการจอง
- room: รหัสห้องจากรายการข้างบน
- booking_type: "single" (จองครั้งเดียว) หรือ "recurring" (จองต่อเนื่องหลายวัน)
- purpose_type: "Teaching" (สอนปกติ/ชดเชย/เสริม) หรือ "Training" (จัดอบรม/จัดติว)
- start_time: เวลาเริ่มต้น รูปแบบ HH:MM
- end_time: เวลาสิ้นสุด รูปแบบ HH:MM

### ถ้า booking_type = "single"
- date: วันที่ รูปแบบ YYYY-MM-DD

### ถ้า booking_type = "recurring"
- start_date: วันที่เริ่ม รูปแบบ YYYY-MM-DD
- end_date: วันที่สิ้นสุด รูปแบบ YYYY-MM-DD
- days_of_week: รายการวัน เช่น [0] หรือ [1,3] (จันทร์=0, อังคาร=1, พุธ=2, พฤหัสบดี=3, ศุกร์=4)

### ถ้า purpose_type = "Teaching"
- course_code: รหัสวิชา เช่น "CN334"
- course_name: ชื่อวิชา
- program: "Bachelor" (ปริญญาตรีภาคปกติ) / "Master" (ปริญญาโท) / "TEP_TEPE" / "TU_PINE"

### ถ้า purpose_type = "Training"
- training_topic: ชื่อเรื่องอบรม/ติว

## สามประเภทของ action
- action = "book"        : อาจารย์ต้องการจองห้อง
- action = "check"       : อาจารย์ต้องการตรวจสอบว่าห้องว่างไหม / ดูตารางห้อง
- action = "my_bookings" : อาจารย์ต้องการดูรายการจองของตัวเอง

## กฎการทำงาน (action = "book")
1. ถ้าข้อมูลครบตั้งแต่ข้อความแรก ให้ตั้ง is_complete = true ทันที ไม่ต้องถามซ้ำ
2. ถ้าข้อมูลยังไม่ครบ ให้ถามข้อมูลที่ขาดทั้งหมดในข้อความเดียว ดังนี้:
   - ห้องที่ต้องการ (406-3 / 406-5 / 408-1 / 408-2/1 / 408-2/2)
   - ประเภทการจอง: ครั้งเดียว หรือ ต่อเนื่อง (ถ้าต่อเนื่อง: ช่วงวันที่ + วันในสัปดาห์)
   - วันที่ และ เวลาเริ่ม–สิ้นสุด
   - วัตถุประสงค์: สอน หรือ อบรม/ติว
     • ถ้าสอน: รหัสวิชา / ชื่อวิชา / หลักสูตร (ป.ตรีปกติ / ป.โท / TEP_TEPE / TU_PINE)
     • ถ้าอบรม: ชื่อเรื่องอบรม/ติว
3. is_complete = true เมื่อข้อมูลครบ ให้ reply_message ว่า "ระบบได้รับข้อมูลการจองแล้วค่ะ และจะส่งเรื่องให้ Admin อนุมัติต่อไป 🙏"
4. ห้ามยืนยันหรืออนุมัติการจองด้วยตัวเอง

## กฎการทำงาน (action = "check")
1. สกัด check_date (บังคับ), check_room (ถ้าระบุ), check_start + check_end (ถ้าถามช่วงเวลาเฉพาะ)
2. check_ready = true เมื่อมี check_date (แม้ไม่มี check_room ก็ตรวจทุกห้องได้)
3. is_complete = false เสมอ
4. reply_message ใส่ว่า "กำลังตรวจสอบตารางห้องค่ะ..."

## กฎการทำงาน (action = "my_bookings")
1. ตั้ง my_bookings_ready = true ทันที ไม่ต้องถามข้อมูลเพิ่ม
2. is_complete = false เสมอ
3. reply_message ใส่ว่า "กำลังดึงข้อมูลการจองค่ะ..."

## กฎทั่วไป
- ห้ามอ้างห้องที่ไม่อยู่ในรายการ

## บุคลิก
เป็นมิตร สุภาพ กระชับ ใช้คำลงท้าย "ค่ะ"

## รูปแบบ Output (JSON เท่านั้น)
{{
  "action": <"book" | "check" | "my_bookings">,
  "is_complete": <true | false>,
  "check_ready": <true เมื่อ action=check และมี check_date | false>,
  "my_bookings_ready": <true เมื่อ action=my_bookings | false>,
  "reply_message": "<ข้อความตอบกลับ>",
  "extracted_data": {{
    "booking_type": <"single" | "recurring" | null>,
    "room": <"406-3" | null>,
    "purpose_type": <"Teaching" | "Training" | null>,
    "date": <"YYYY-MM-DD" สำหรับ single | null>,
    "start_date": <"YYYY-MM-DD" สำหรับ recurring | null>,
    "end_date": <"YYYY-MM-DD" สำหรับ recurring | null>,
    "days_of_week": <[0,1,2] สำหรับ recurring | null>,
    "start_time": <"HH:MM" | null>,
    "end_time": <"HH:MM" | null>,
    "course_code": <รหัสวิชา | null>,
    "course_name": <ชื่อวิชา | null>,
    "program": <"Bachelor" | "Master" | "TEP_TEPE" | "TU_PINE" | null>,
    "training_topic": <ชื่อเรื่อง | null>,
    "check_date": <"YYYY-MM-DD" | null>,
    "check_room": <รหัสห้อง | null>,
    "check_start": <"HH:MM" | null>,
    "check_end": <"HH:MM" | null>
  }}
}}
"""

# ── FAQ pattern matching ───────────────────────────────────────────────────────

_ROOM_LIST_REPLY = (
    "ห้องที่มีในระบบ Roomasat มีทั้งหมด 5 ห้องค่ะ\n\n"
    "📋 ห้องประชุม\n"
    "• 406-3   – ห้องประชุม 1  (60 ที่นั่ง)\n"
    "• 406-5   – ห้องประชุม 2  (15 ที่นั่ง)\n"
    "• 408-1   – ห้องประชุม 3  (10 ที่นั่ง)\n\n"
    "🎓 ห้องบรรยาย\n"
    "• 408-2/1 – ห้องบรรยาย 1 (20 ที่นั่ง)\n"
    "• 408-2/2 – ห้องบรรยาย 2 (20 ที่นั่ง)\n\n"
    "อาจารย์ต้องการจองห้องไหนคะ?"
)

_EMPTY_SLOTS = {
    "booking_type": None, "room": None, "purpose_type": None,
    "date": None, "start_date": None, "end_date": None, "days_of_week": None,
    "start_time": None, "end_time": None,
    "course_code": None, "course_name": None, "program": None, "training_topic": None,
}

_FAQ_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (
        re.compile(
            r"มีห้อง(อะไร|ไหน|ใดบ้าง)?บ้าง|(?<!จอง)ห้อง(อะไร|ทั้งหมด|มีอะไร)|รายชื่อห้อง|(?<!การ)ดูห้อง|ห้องว่าง(มีอะไร|อะไรบ้าง)?",
            re.IGNORECASE,
        ),
        {"is_complete": False, "reply_message": _ROOM_LIST_REPLY, "extracted_data": _EMPTY_SLOTS},
    ),
]


def _faq_response(text: str) -> dict | None:
    """Return a fresh copy of a static response if text matches a known FAQ pattern, else None."""
    for pattern, response in _FAQ_PATTERNS:
        if pattern.search(text):
            # Return a copy so callers cannot mutate the shared template dict.
            return {**response, "extracted_data": {**response["extracted_data"]}}
    return None

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
    Run one turn of the booking conversation through Gemini 2.5 Flash.

    Conversation history is stored in Django's cache keyed by line_user_id.
    Cleared when is_complete=true; refreshed with a 5-minute TTL otherwise.

    NOTE: Django's default LocMemCache is per-process. Use Redis/Memcached
    for multi-worker deployments.
    """
    # Return a fixed response for common FAQ questions without calling the LLM.
    faq = _faq_response(current_message)
    if faq:
        return faq

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    cache_key = _CACHE_KEY_TEMPLATE.format(line_user_id)
    history: list[dict] = cache.get(cache_key, [])

    # Append the new user turn before calling the model
    history.append({"role": "user", "parts": [current_message]})

    today = date.today().strftime("%Y-%m-%d")
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION_TEMPLATE.format(today=today),
        response_mime_type="application/json",
        temperature=0.1,
    )

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
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
