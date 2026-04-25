from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from bookings.models import Booking, User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@login_required
def dashboard_view(request):
    if request.user.role == "Admin":
        bookings = Booking.objects.filter(status="Pending").order_by("start_time")
        template = "dashboard/admin_dashboard.html"
    else:
        bookings = Booking.objects.filter(user=request.user).order_by("-created_at")
        template = "dashboard/user_dashboard.html"

    return render(request, template, {"bookings": bookings, "now": timezone.now()})


@login_required
def update_status(request, booking_id, new_status):
    if request.user.role != "Admin":
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงส่วนนี้")
        return redirect("dashboard")

    try:
        booking = Booking.objects.get(id=booking_id)
        if new_status in ["Approved", "Rejected"]:
            booking.status = new_status
            booking.save()

            target_email = booking.user.email

            if target_email:
                status_th = "อนุมัติ" if new_status == "Approved" else "ปฏิเสธ"
                subject = f"แจ้งผลการจองห้อง {booking.room.room_id}"
                message = (
                    f"สวัสดีครับ อาจารย์ {booking.user.first_name or booking.user.username}\n\n"
                    f'คำขอจองห้อง {booking.room.room_id} ในวันที่ {booking.start_time.strftime("%d/%m/%Y")} '
                    f'ได้รับการ "{status_th}" เรียบร้อยแล้วครับ\n\n'
                    f"ตรวจสอบรายละเอียดได้ที่หน้า Dashboard ของคุณ"
                )

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [target_email],
                    fail_silently=True,
                )

            messages.success(request, f"เปลี่ยนสถานะการจองเป็น {new_status} เรียบร้อยแล้ว")
    except Booking.DoesNotExist:
        messages.error(request, "ไม่พบรายการจองดังกล่าว")

    return redirect("dashboard")


@login_required
def cancel_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)

        if booking.start_time > timezone.now():
            booking.status = "Cancelled"
            booking.save()

            admin_emails = User.objects.filter(role="Admin").values_list(
                "email", flat=True
            )
            admin_emails = [e for e in admin_emails if e]

            if admin_emails:
                subject = f"[ยกเลิกการจอง] คิวห้อง {booking.room.room_id} ถูกยกเลิก"
                message = (
                    f"เรียน Admin,\n\n"
                    f"อาจารย์ {request.user.first_name} ได้ทำการยกเลิกการจองห้อง {booking.room.room_id}\n"
                    f'สำหรับช่วงเวลา: {booking.start_time.strftime("%d/%m/%Y %H:%M")}\n\n'
                    f"ระบบได้ทำการคืนคิวว่างให้กับห้องดังกล่าวแล้ว"
                )
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    admin_emails,
                    fail_silently=True,
                )

            messages.success(request, "ยกเลิกการจองเรียบร้อยแล้ว")
        else:
            messages.error(request, "ไม่สามารถยกเลิกการจองที่ถึงกำหนดเวลาหรือผ่านไปแล้วได้")

    except Booking.DoesNotExist:
        messages.error(request, "ไม่พบรายการจอง หรือคุณไม่มีสิทธิ์ยกเลิกรายการนี้")

    return redirect("dashboard")
