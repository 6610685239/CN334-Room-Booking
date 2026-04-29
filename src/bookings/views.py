import requests
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.conf import settings
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime, parse_date
from django.core.exceptions import ValidationError
from .models import User, Room, Booking
from django.http import JsonResponse
from django.utils.timezone import localtime


def tu_login_view(request):
    if request.user.is_authenticated:
        return redirect("book_room")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        url = "https://restapi.tu.ac.th/api/v1/auth/ad/verify"
        headers = {
            "Content-Type": "application/json",
            "Application-Key": settings.TU_API_KEY,
        }
        data = {"UserName": username, "PassWord": password}

        try:
            response = requests.post(url, json=data, headers=headers)
            result = response.json()

            if response.status_code == 200 and result.get("status") == True:
                api_username = result.get("username")
                display_name = result.get("displayname_th", "")
                api_email = result.get("email")

                user, created = User.objects.get_or_create(username=api_username)

                user.first_name = display_name
                if api_email:
                    user.email = api_email

                if created:
                    user.role = "Lecturer"

                user.save()

                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )

                return redirect("book_room")
            else:
                messages.error(request, "ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")

        except Exception as e:
            print(f"CRITICAL ERROR in Login: {e}")
            messages.error(request, "เกิดข้อผิดพลาดในการสร้างเซสชันเข้าสู่ระบบ")
            return render(request, "bookings/login.html")

    return render(request, "bookings/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def create_booking_view(request):
    rooms = Room.objects.filter(is_active=True).order_by('room_id')

    if request.method == "POST":
        try:
            room = Room.objects.get(room_id=request.POST.get("room"), is_active=True)

            booking = Booking(
                user=request.user,
                room=room,
                purpose_type=request.POST.get("purpose_type"),
                course_code=request.POST.get("course_code"),
                course_name=request.POST.get("course_name"),
                program=request.POST.get("program"),
                training_topic=request.POST.get("training_topic"),
                start_time=parse_datetime(request.POST.get("start_time")),
                end_time=parse_datetime(request.POST.get("end_time")),
                status="Pending",
            )

            booking.full_clean()
            booking.save()

            subject = f"มีการขอจองห้องใหม่: ห้อง {room.room_id}"
            message = (
                f"ผู้ใช้งาน {request.user.username} ได้ขอจองห้อง {room.room_id}\n"
                f'วันที่: {booking.start_time.strftime("%d/%m/%Y %H:%M")} ถึง {booking.end_time.strftime("%H:%M")}\n'
                f"กรุณาตรวจสอบและดำเนินการในระบบ"
            )

            admin_emails = User.objects.filter(role="Admin").values_list(
                "email", flat=True
            )
            admin_emails = [e for e in admin_emails if e]

            if admin_emails:
                subject = f"[แจ้งเตือน] คำขอจองห้องใหม่: {booking.room.room_id}"
                message = (
                    f"อาจารย์ {request.user.first_name or request.user.username} ได้ส่งคำขอจองห้อง\n"
                    f"ห้อง: {booking.room.room_id}\n"
                    f'วันที่: {booking.start_time.strftime("%d/%m/%Y %H:%M")} เป็นต้นไป\n\n'
                    f'กรุณาตรวจสอบที่ระบบ Dashboard: {request.build_absolute_uri("/dashboard/")}'
                )

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    admin_emails,
                    fail_silently=True,
                )

            messages.success(request, "ส่งคำขอจองห้องสำเร็จ! กรุณารอการอนุมัติ")
            return redirect("book_room")

        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Room.DoesNotExist:
            messages.error(request, "ห้องนี้ปิดใช้งานหรือไม่พร้อมสำหรับการจอง")
        except Exception as e:
            messages.error(request, "เกิดข้อผิดพลาด หรือรูปแบบวันที่ไม่ถูกต้อง")

    initial_room = request.GET.get("room", "")
    initial_start = request.GET.get("start", "")
    initial_end = request.GET.get("end", "")

    context = {
        "rooms": rooms,
        "initial_room": initial_room,
        "initial_start": initial_start,
        "initial_end": initial_end,
    }

    return render(request, "bookings/booking_form.html", context)


@login_required
def api_get_booked_slots(request):
    room_id = request.GET.get("room_id")
    date_str = request.GET.get("date")

    if not room_id or not date_str:
        return JsonResponse({"booked_slots": []})

    try:
        target_date = parse_date(date_str)

        bookings = Booking.objects.filter(
            room__room_id=room_id,
            start_time__date=target_date,
            status__in=["Pending", "Approved"],
        )

        booked_slots = []
        for b in bookings:
            booked_slots.append(
                {
                    "start": localtime(b.start_time).strftime("%H:%M"),
                    "end": localtime(b.end_time).strftime("%H:%M"),
                }
            )

        return JsonResponse({"booked_slots": booked_slots})

    except Exception as e:
        print(f"CRITICAL ERROR in api_get_booked_slots: {e}")
        return JsonResponse({"error": str(e)}, status=500)


def api_get_bookings(request):
    room_id = request.GET.get("room_id")

    bookings = Booking.objects.filter(status__in=["Pending", "Approved"])

    if room_id:
        bookings = bookings.filter(room__room_id=room_id)

    events = []
    for b in bookings:
        event_color = "#f39c12" if b.status == "Pending" else "#27ae60"

        title = f"[{b.room.room_id}] "
        if b.purpose_type == "Teaching":
            title += f"สอน: {b.course_code}"
        else:
            title += f"อบรม: {b.training_topic[:15]}..."

        events.append(
            {
                "id": b.id,
                "title": title,
                "start": localtime(b.start_time).strftime("%Y-%m-%dT%H:%M:%S"),
                "end": localtime(b.end_time).strftime("%Y-%m-%dT%H:%M:%S"),
                "color": event_color,
                "description": b.get_purpose_type_display(),
                "extendedProps": {"status": b.status, "room_name": b.room.name, "room_id": b.room.room_id},
            }
        )

    return JsonResponse(events, safe=False)


@login_required
def calendar_view(request):
    rooms = Room.objects.filter(is_active=True).order_by('room_id')
    return render(request, "bookings/calendar.html", {"rooms": rooms})
