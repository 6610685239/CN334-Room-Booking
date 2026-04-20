import requests
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ValidationError
from .models import User, Room, Booking


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

                user, created = User.objects.get_or_create(username=api_username)

                if created:
                    user.role = "Lecturer"
                    user.first_name = display_name
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
    rooms = Room.objects.all()

    if request.method == "POST":
        room_id = request.POST.get("room")
        purpose = request.POST.get("purpose")
        start_time_str = request.POST.get("start_time")
        end_time_str = request.POST.get("end_time")

        try:
            room = Room.objects.get(room_id=room_id)
            booking = Booking(
                user=request.user,
                room=room,
                purpose=purpose,
                start_time=parse_datetime(start_time_str),
                end_time=parse_datetime(end_time_str),
                status="Pending",
            )

            booking.full_clean()
            booking.save()

            messages.success(request, "ส่งคำขอจองห้องสำเร็จ กรุณารอการอนุมัติจาก Admin")
            return redirect("book_room")

        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Room.DoesNotExist:
            messages.error(request, "ไม่พบห้องที่ต้องการจอง")
        except Exception as e:
            messages.error(request, "รูปแบบวันที่/เวลาไม่ถูกต้อง กรุณาลองใหม่")

    return render(request, "bookings/booking_form.html", {"rooms": rooms})
