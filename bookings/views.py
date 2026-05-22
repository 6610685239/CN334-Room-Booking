import requests
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.conf import settings
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime, parse_date
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from .models import User, Room, Booking
from django.http import JsonResponse
from django.utils.timezone import localtime
from django.utils import timezone
from datetime import datetime, timedelta


def tu_login_view(request):
    if request.user.is_authenticated:
        if "Line/" in request.META.get("HTTP_USER_AGENT", ""):
            return render(request, "bookings/liff_success.html", {
                "liff_id": settings.LIFF_ID,
                "display_name": request.user.first_name or request.user.username,
            })
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

        # Accept LINE user ID from POST body (injected by LIFF JS) or URL param
        line_user_id = (
            request.POST.get("line_user_id") or request.GET.get("line_user_id") or ""
        ).strip() or None

        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
        except requests.exceptions.Timeout:
            messages.error(request, "ไม่สามารถเชื่อมต่อระบบยืนยันตัวตนได้ (หมดเวลา) กรุณาลองใหม่อีกครั้ง")
            return render(request, "bookings/login.html")
        except requests.exceptions.ConnectionError:
            messages.error(request, "ไม่สามารถเชื่อมต่อระบบยืนยันตัวตนได้ กรุณาลองใหม่อีกครั้ง")
            return render(request, "bookings/login.html")

        try:
            result = response.json()
        except ValueError:
            print(f"TU API returned non-JSON response: {response.status_code} {response.text[:200]}")
            messages.error(request, "ระบบยืนยันตัวตนตอบสนองผิดปกติ กรุณาลองใหม่อีกครั้ง")
            return render(request, "bookings/login.html")

        try:
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

                # Link LINE account only when a fresh LINE user ID is provided
                # and this user does not already have one linked.
                if line_user_id and not user.line_user_id:
                    user.line_user_id = line_user_id

                try:
                    user.save()
                except IntegrityError:
                    # Another account already holds this line_user_id — skip linking.
                    user.line_user_id = None
                    user.save()
                    messages.warning(
                        request,
                        "LINE account นี้ถูกผูกกับบัญชีอื่นแล้ว ระบบจะเข้าสู่ระบบโดยไม่ผูก LINE",
                    )

                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )

                return redirect("dashboard")
            else:
                messages.error(request, "ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")

        except Exception as e:
            print(f"CRITICAL ERROR in Login: {e}")
            messages.error(request, "เกิดข้อผิดพลาดในการสร้างเซสชันเข้าสู่ระบบ")
            return render(request, "bookings/login.html", {"liff_id": settings.LIFF_ID})

    return render(request, "bookings/login.html", {"liff_id": settings.LIFF_ID})


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def create_booking_view(request):
    rooms = Room.objects.filter(is_active=True).order_by("room_id")

    if request.method == "POST":
        room_id = request.POST.get("room")
        purpose_type = request.POST.get("purpose_type")
        course_code = request.POST.get("course_code")
        course_name = request.POST.get("course_name")
        program = request.POST.get("program")
        training_topic = request.POST.get("training_topic")

        # ฟิลด์ที่เพิ่มมาใหม่สำหรับแยกว่าเป็นการจองแบบไหน
        hidden_start = request.POST.get("start_time")
        hidden_end = request.POST.get("end_time")
        booking_type = request.POST.get("booking_type", "single")

        if not hidden_start or not hidden_end:
            messages.error(request, "กรุณาเลือกช่วงเวลาให้ครบถ้วน")
            return redirect("book_room")

        try:
            room = Room.objects.get(room_id=room_id, is_active=True)
            base_start_dt = parse_datetime(hidden_start)
            base_end_dt = parse_datetime(hidden_end)

            if base_start_dt is None or base_end_dt is None:
                messages.error(
                    request, "รูปแบบวันที่/เวลาไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
                )
                return redirect("book_room")

            if timezone.is_naive(base_start_dt):
                base_start_dt = timezone.make_aware(base_start_dt)
            if timezone.is_naive(base_end_dt):
                base_end_dt = timezone.make_aware(base_end_dt)

            now = timezone.now()
            created_bookings = []  # เก็บลิสต์การจองที่สร้างสำเร็จเพื่อเอาไปส่งอีเมล
            conflict_count = 0

            # ---------------------------------------------------------
            # กรณี 1: จองแบบครั้งเดียว (Single Booking)
            # ---------------------------------------------------------
            if booking_type == "single":
                # เช็คว่าเวลาที่จองผ่านมาแล้วหรือเปล่า
                if base_start_dt <= now:
                    messages.error(
                        request,
                        "ไม่สามารถจองเวลาที่ผ่านมาแล้วได้",
                    )
                    return render(
                        request,
                        "bookings/booking_form.html",
                        {
                            "rooms": rooms,
                            "form_data": request.POST,
                        },
                    )

                # เช็คคิวชน
                conflict = Booking.objects.filter(
                    room=room,
                    status__in=["Pending", "Approved"],
                    start_time__lt=base_end_dt,
                    end_time__gt=base_start_dt,
                ).exists()

                if conflict:
                    messages.error(
                        request,
                        "ขออภัย ช่วงเวลาที่คุณเลือกมีผู้จองแล้ว กรุณาเลือกเวลาอื่นครับ",
                    )
                    return redirect("book_room")

                booking = Booking.objects.create(
                    user=request.user,
                    room=room,
                    purpose_type=purpose_type,
                    course_code=course_code,
                    course_name=course_name,
                    program=program,
                    training_topic=training_topic,
                    start_time=base_start_dt,
                    end_time=base_end_dt,
                    status="Pending",
                )
                created_bookings.append(booking)
                messages.success(
                    request, f"ส่งคำขอจองห้อง {room.name} สำเร็จ! กรุณารอการอนุมัติ"
                )

            # ---------------------------------------------------------
            # กรณี 2: จองแบบต่อเนื่อง (Recurring Booking)
            # ---------------------------------------------------------
            elif booking_type == "recurring":
                recur_start = request.POST.get("recur_start_date")
                recur_end = request.POST.get("recur_end_date")
                days_of_week = request.POST.getlist("days_of_week")

                if not recur_start or not recur_end or not days_of_week:
                    messages.error(
                        request,
                        "กรุณาระบุวันที่เริ่มต้น สิ้นสุด และวันในสัปดาห์ให้ครบถ้วน",
                    )
                    return redirect("book_room")

                start_date = parse_date(recur_start)
                end_date = parse_date(recur_end)
                selected_days = [int(day) for day in days_of_week]

                current_date = start_date

                # วนลูปสร้างรายการจองตามวันที่เลือก
                while current_date <= end_date:
                    if current_date.weekday() in selected_days:
                        target_start = timezone.make_aware(
                            datetime.combine(current_date, base_start_dt.time())
                        )
                        target_end = timezone.make_aware(
                            datetime.combine(current_date, base_end_dt.time())
                        )

                        # ข้ามวัน/เวลาที่ผ่านมาแล้ว
                        if target_start <= now:
                            conflict_count += 1
                            current_date += timedelta(days=1)
                            continue

                        conflict = Booking.objects.filter(
                            room=room,
                            status__in=["Pending", "Approved"],
                            start_time__lt=target_end,
                            end_time__gt=target_start,
                        ).exists()

                        if not conflict:
                            bk = Booking.objects.create(
                                user=request.user,
                                room=room,
                                purpose_type=purpose_type,
                                course_code=course_code,
                                course_name=course_name,
                                program=program,
                                training_topic=training_topic,
                                start_time=target_start,
                                end_time=target_end,
                                status="Pending",
                            )
                            created_bookings.append(bk)
                        else:
                            conflict_count += 1

                    current_date += timedelta(days=1)

                if len(created_bookings) > 0:
                    msg = f"สร้างการจองต่อเนื่องสำเร็จ {len(created_bookings)} รายการ"
                    if conflict_count > 0:
                        msg += f" (ระบบข้ามวันที่คิวชนไป {conflict_count} วัน)"
                    messages.success(request, msg)
                else:
                    messages.error(
                        request,
                        "ไม่สามารถสร้างการจองได้เลย เนื่องจากคิวเต็ม หรือช่วงวันที่ไม่ตรงกับวันในสัปดาห์",
                    )
                    return redirect("book_room")

            # ---------------------------------------------------------
            # ส่งอีเมลแจ้งเตือน Admin (ใช้โค้ดเดิมของคุณ)
            # ---------------------------------------------------------
            if len(created_bookings) > 0:
                admin_emails = User.objects.filter(role="Admin").values_list(
                    "email", flat=True
                )
                admin_emails = [e for e in admin_emails if e]

                if admin_emails:
                    first_bk = created_bookings[0]  # อ้างอิงเวลาจากคิวแรก
                    subject = f"[แจ้งเตือน] คำขอจองห้องใหม่: {first_bk.room.room_id}"

                    if booking_type == "recurring":
                        message = (
                            f"อาจารย์ {request.user.first_name or request.user.username} ได้ส่งคำขอจองห้องแบบต่อเนื่อง\n"
                            f"ห้อง: {first_bk.room.room_id}\n"
                            f"จำนวน: {len(created_bookings)} รายการ\n"
                            f'เริ่มตั้งแต่วันที่: {first_bk.start_time.strftime("%d/%m/%Y %H:%M")}\n\n'
                            f'กรุณาตรวจสอบที่ระบบ Dashboard: {request.build_absolute_uri("/dashboard/")}'
                        )
                    else:
                        message = (
                            f"อาจารย์ {request.user.first_name or request.user.username} ได้ส่งคำขอจองห้อง\n"
                            f"ห้อง: {first_bk.room.room_id}\n"
                            f'วันที่: {first_bk.start_time.strftime("%d/%m/%Y %H:%M")} เป็นต้นไป\n\n'
                            f'กรุณาตรวจสอบที่ระบบ Dashboard: {request.build_absolute_uri("/dashboard/")}'
                        )

                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        admin_emails,
                        fail_silently=True,
                    )

            return redirect("dashboard")

        except Room.DoesNotExist:
            messages.error(request, "ห้องนี้ปิดใช้งานหรือไม่พร้อมสำหรับการจอง")
        except Exception as e:
            print(f"Error booking: {e}")
            messages.error(
                request, "เกิดข้อผิดพลาดในการบันทึกข้อมูล กรุณาตรวจสอบความถูกต้อง"
            )

    # --- ส่วนการส่งค่ากลับไป render หน้าเว็บ (โค้ดเดิม) ---
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
                "extendedProps": {
                    "status": b.status,
                    "room_name": b.room.name,
                    "room_id": b.room.room_id,
                },
            }
        )

    return JsonResponse(events, safe=False)


@login_required
def calendar_view(request):
    rooms = Room.objects.filter(is_active=True).order_by("room_id")
    return render(request, "bookings/calendar.html", {"rooms": rooms})
