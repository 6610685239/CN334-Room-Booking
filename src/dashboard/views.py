from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from bookings.models import Booking


@login_required
def dashboard_view(request):
    if request.user.role == "Admin":
        bookings = Booking.objects.filter(status="Pending").order_by("start_time")
        template = "dashboard/admin_dashboard.html"
    else:
        bookings = Booking.objects.filter(user=request.user).order_by("-created_at")
        template = "dashboard/user_dashboard.html"

    return render(request, template, {"bookings": bookings})


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
            messages.success(request, f"เปลี่ยนสถานะการจองเป็น {new_status} เรียบร้อยแล้ว")
    except Booking.DoesNotExist:
        messages.error(request, "ไม่พบรายการจองดังกล่าว")

    return redirect("dashboard")
