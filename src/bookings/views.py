import requests
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.conf import settings
from django.contrib import messages
from .models import User, Room, Booking
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ValidationError


def tu_login_view(request):
    # ถ้า User ล็อกอินอยู่แล้ว ให้เด้งไปหน้า Dashboard เลย
    if request.user.is_authenticated:
        return redirect("book")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # 1. ยิง Request ไปที่ TU REST API
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

                # 1. ใช้ username และชื่อที่ได้จาก API ตรงๆ เพื่อความถูกต้อง
                api_username = result.get("username")
                display_name = result.get("displayname_th", "")

                # 2. สร้างหรือดึงข้อมูล User ในฐานข้อมูลเรา
                user, created = User.objects.get_or_create(username=api_username)

                if created:
                    user.role = "Lecturer"  # หรือเปลี่ยนเป็น 'Student' ถ้าต้องการเพิ่มใน model
                    user.first_name = display_name
                    user.save()

                # 3. ระบุ backend ให้ชัดเจน (จุดนี้มักจะทำให้โค้ดพังถ้าไม่ใส่)
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )

                return redirect("book")
            else:
                messages.error(request, "ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")

        except Exception as e:
            print(f"CRITICAL ERROR in Login: {e}")
            messages.error(request, "เกิดข้อผิดพลาดในการสร้างเซสชันเข้าสู่ระบบ")
            # เพิ่มบรรทัดนี้ลงไป เพื่อให้มันเด้งกลับไปหน้า Login พร้อมโชว์ข้อความ Error
            return render(request, "bookings/login.html")


@login_required  # บังคับว่าต้อง Login ก่อนถึงจะเข้าหน้านี้ได้
def create_booking_view(request):
    rooms = Room.objects.all()  # ดึงข้อมูลห้องทั้งหมดมาทำ Dropdown

    if request.method == "POST":
        room_id = request.POST.get("room")
        purpose = request.POST.get("purpose")
        start_time_str = request.POST.get("start_time")
        end_time_str = request.POST.get("end_time")

        try:
            room = Room.objects.get(room_id=room_id)

            # สร้างตัวแปรจำลองขึ้นมาก่อน (ยังไม่เซฟลงฐานข้อมูล)
            booking = Booking(
                user=request.user,
                room=room,
                purpose=purpose,
                start_time=parse_datetime(start_time_str),
                end_time=parse_datetime(end_time_str),
                status="Pending",  # ให้สถานะเริ่มต้นเป็นรออนุมัติเสมอ
            )

            # สั่งให้มันเช็คกฎในฟังก์ชัน clean() ก่อน ถ้าผ่านถึงจะเซฟ
            booking.full_clean()
            booking.save()

            messages.success(request, "ส่งคำขอจองห้องสำเร็จ กรุณารอการอนุมัติจาก Admin")
            return redirect("dashboard")

        except ValidationError as e:
            # ถ้าติด Conflict หรือเวลาผิด มันจะเด้งมาที่นี่
            for message in e.messages:
                messages.error(request, message)
        except Room.DoesNotExist:
            messages.error(request, "ไม่พบห้องที่ต้องการจอง")
        except Exception as e:
            messages.error(request, "รูปแบบวันที่/เวลาไม่ถูกต้อง กรุณาลองใหม่")

    return render(request, "bookings/booking_form.html", {"rooms": rooms})
