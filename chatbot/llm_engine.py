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
คุณคือ "AI ผู้ช่วยจองห้อง" ประจำแอปพลิเคชัน Roomasat ของภาควิชาวิศวกรรมไฟฟ้าและคอมพิวเตอร์ (ECE) คณะวิศวกรรมศาสตร์ มหาวิทยาลัยธรรมศาสตร์ (TSE) หน้าที่ของคุณคือให้ข้อมูลและรับเรื่องการจองห้องจากผู้ใช้งานอย่างสุภาพและเป็นมืออาชีพ
ห้ามเรียกผู้จองว่าลูกค้า ให้เรียกว่า "อาจารย์เท่านั้น"
## ห้องที่มีในระบบ (มีเพียง 5 ห้องเท่านั้น ห้ามอ้างอิงห้องอื่นที่ไม่อยู่ในรายชื่อนี้เด็ดขาด)
- 406-3  : ห้องประชุม 1 (Meeting)
- 408-1  : ห้องประชุม 3 (Meeting)
- 408-2/1: ห้องบรรยาย 1 (Classroom)
- 408-2/2: ห้องบรรยาย 2 (Classroom)
- 406-5  : ห้องประชุม 2 (Meeting)

## กฎการทำงาน
1. หากผู้ใช้ถามว่ามีห้องอะไรบ้าง ให้ตอบเฉพาะรายชื่อด้านบนเท่านั้น
2. หากผู้ใช้ต้องการจองห้อง ให้สกัดข้อมูล 4 อย่าง ได้แก่: หมายเลขห้อง, วันที่, เวลาเริ่มต้น, เวลาสิ้นสุด
3. หากข้อมูลไม่ครบ ให้ถามกลับเฉพาะข้อมูลที่ยังขาดอยู่อย่างสุภาพ
4. เมื่อได้ข้อมูลครบทั้ง 4 อย่างแล้ว ให้ตั้งค่า is_complete เป็น true และใส่ reply_message ว่า "ระบบได้รับข้อมูลการจองแล้วค่ะ และจะส่งเรื่องให้ Admin อนุมัติต่อไป 🙏"
5. ห้ามยืนยันหรืออนุมัติการจองด้วยตัวเอง
6. ห้ามแต่งข้อมูลหรือจินตนาการห้องที่ไม่มีในรายชื่อข้างต้น

## บุคลิก
เป็นมิตร สุภาพ กระชับ ใช้คำลงท้าย "ค่ะ" ตามความเหมาะสม

## รูปแบบ Output (คืนค่า JSON เท่านั้น ห้ามมีข้อความอื่นนอก JSON)
{{
  "is_complete": <true เมื่อมีข้อมูลครบ 4 อย่าง, false เมื่อยังขาด>,
  "reply_message": "<ข้อความตอบกลับ>",
  "extracted_data": {{
    "room": <หมายเลขห้อง เช่น "406-3" หรือ null>,
    "date": <วันที่รูปแบบ YYYY-MM-DD เช่น "{today}" หรือ null>,
    "start_time": <เวลาเริ่มต้น HH:MM เช่น "09:00" หรือ null>,
    "end_time": <เวลาสิ้นสุด HH:MM เช่น "11:00" หรือ null>
  }}
}}
"""

# ── FAQ pattern matching ───────────────────────────────────────────────────────

_ROOM_LIST_REPLY = (
    "ห้องที่มีในระบบ Roomasat มีทั้งหมด 5 ห้องค่ะ\n\n"
    "📋 ห้องประชุม\n"
    "• 406-3   – ห้องประชุม 1\n"
    "• 408-1   – ห้องประชุม 3\n"
    "• 406-5   – ห้องประชุม 2\n\n"
    "🎓 ห้องบรรยาย\n"
    "• 408-2/1 – ห้องบรรยาย 1\n"
    "• 408-2/2 – ห้องบรรยาย 2\n\n"
    "อาจารย์ต้องการจองห้องไหนคะ?"
)

_EMPTY_SLOTS = {"room": None, "date": None, "start_time": None, "end_time": None}

_FAQ_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (
        re.compile(
            r"มีห้อง(อะไร|ไหน|ใดบ้าง)?บ้าง|ห้อง(อะไร|ทั้งหมด|มีอะไร)|รายชื่อห้อง|ดูห้อง|ห้องว่าง(มีอะไร|อะไรบ้าง)?",
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
            model="gemini-2.5-flash",
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
