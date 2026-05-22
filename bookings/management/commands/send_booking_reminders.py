from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Booking
from chatbot.views import push_line_message


class Command(BaseCommand):
    help = "Send reminder emails (and LINE pushes) for approved bookings starting tomorrow."

    def handle(self, *args, **options):
        tomorrow = (timezone.now() + timedelta(days=1)).date()

        bookings = Booking.objects.filter(
            status="Approved",
            start_time__date=tomorrow,
        ).select_related("user", "room")

        sent_email = 0
        sent_line = 0

        for booking in bookings:
            display_name = booking.user.first_name or booking.user.username
            date_fmt = booking.start_time.strftime("%d/%m/%Y")
            time_fmt = (
                f"{booking.start_time.strftime('%H:%M')} – "
                f"{booking.end_time.strftime('%H:%M')} น."
            )

            if booking.user.email:
                send_mail(
                    subject=f"[เตือนความจำ] การจองห้อง {booking.room.room_id} พรุ่งนี้",
                    message=(
                        f"สวัสดีครับ อาจารย์ {display_name}\n\n"
                        f"เตือนความจำ: อาจารย์มีการจองห้องในวันพรุ่งนี้\n\n"
                        f"ห้อง: {booking.room.room_id} – {booking.room.name}\n"
                        f"วันที่: {date_fmt}\n"
                        f"เวลา: {time_fmt}\n\n"
                        f"หากต้องการยกเลิก กรุณาเข้าสู่ระบบที่หน้า Dashboard ก่อนถึงวันใช้งาน"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[booking.user.email],
                    fail_silently=True,
                )
                sent_email += 1

            if booking.user.line_user_id:
                push_line_message(
                    booking.user.line_user_id,
                    f"🔔 เตือนความจำค่ะ\n"
                    f"อาจารย์ {display_name}\n\n"
                    f"พรุ่งนี้มีการจองห้อง:\n"
                    f"ห้อง: {booking.room.room_id} – {booking.room.name}\n"
                    f"วันที่: {date_fmt}\n"
                    f"เวลา: {time_fmt}",
                )
                sent_line += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders sent for {tomorrow}: {sent_email} email(s), {sent_line} LINE push(es)."
            )
        )
