import requests
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.conf import settings
from django.contrib import messages
from .models import User


def tu_login_view(request):
    # ถ้า User ล็อกอินอยู่แล้ว ให้เด้งไปหน้า Dashboard เลย
    if request.user.is_authenticated:
        return redirect("dashboard")

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

                return redirect("dashboard")
            else:
                messages.error(request, "ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")

        except Exception as e:
            print(f"CRITICAL ERROR in Login: {e}")
            messages.error(request, "เกิดข้อผิดพลาดในการสร้างเซสชันเข้าสู่ระบบ")
            # เพิ่มบรรทัดนี้ลงไป เพื่อให้มันเด้งกลับไปหน้า Login พร้อมโชว์ข้อความ Error
            return render(request, "bookings/login.html")


# สร้าง View ปลอมๆ ไว้รองรับตอน Login เสร็จ
def dashboard_view(request):
    return render(request, "bookings/dashboard.html")
