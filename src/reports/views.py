import csv
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from bookings.models import Booking, Room
from django.http import HttpResponse


@login_required
def report_dashboard(request):
    if request.user.role != "Admin":
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้ารายงานสถิติ")
        return redirect("dashboard")

    now = timezone.now()
    default_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d")
    default_end = now.strftime("%Y-%m-%d")

    start_date_str = request.GET.get("start_date", default_start)
    end_date_str = request.GET.get("end_date", default_end)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)

    approved_bookings = Booking.objects.filter(
        status="Approved", start_time__gte=start_date, start_time__lt=end_date
    )

    rooms = Room.objects.all()
    room_stats = []

    total_bookings = 0
    total_hours = 0.0

    for room in rooms:
        room_bks = approved_bookings.filter(room=room)

        count = room_bks.count()
        total_bookings += count

        hours = 0.0
        for b in room_bks:
            duration = (b.end_time - b.start_time).total_seconds() / 3600.0
            hours += duration

        total_hours += hours

        work_hours_capacity = 264.0
        util_rate = (
            (hours / work_hours_capacity) * 100 if work_hours_capacity > 0 else 0
        )

        room_stats.append(
            {
                "room": room,
                "count": count,
                "hours": round(hours, 2),
                "util_rate": round(util_rate, 2),
            }
        )

    teaching_count = approved_bookings.filter(purpose_type="Teaching").count()
    training_count = approved_bookings.filter(purpose_type="Training").count()

    context = {
        "start_date": start_date_str,
        "end_date": end_date_str,
        "room_stats": room_stats,
        "total_bookings": total_bookings,
        "total_hours": round(total_hours, 2),
        "teaching_count": teaching_count,
        "training_count": training_count,
    }

    return render(request, "reports/report_dashboard.html", context)


@login_required
def export_report_csv(request):
    if request.user.role != "Admin":
        messages.error(request, "คุณไม่มีสิทธิ์ดาวน์โหลดรายงาน")
        return redirect("dashboard")

    now = timezone.now()
    start_date_str = request.GET.get(
        "start_date", now.replace(day=1).strftime("%Y-%m-%d")
    )
    end_date_str = request.GET.get("end_date", now.strftime("%Y-%m-%d"))

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)

    approved_bookings = Booking.objects.filter(
        status="Approved", start_time__gte=start_date, start_time__lt=end_date
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="Room_Report_{start_date_str}_to_{end_date_str}.csv"'
    )

    response.write("\ufeff".encode("utf8"))

    writer = csv.writer(response)

    writer.writerow(
        [
            "รหัสห้อง",
            "ชื่อห้อง",
            "ประเภท",
            "จำนวนการใช้งาน (ครั้ง)",
            "จำนวนชั่วโมงรวม (ชม.)",
            "อัตราการใช้งาน (%)",
        ]
    )

    rooms = Room.objects.all()
    for room in rooms:
        room_bks = approved_bookings.filter(room=room)
        count = room_bks.count()

        hours = 0.0
        for b in room_bks:
            hours += (b.end_time - b.start_time).total_seconds() / 3600.0

        work_hours_capacity = 264.0
        util_rate = (
            (hours / work_hours_capacity) * 100 if work_hours_capacity > 0 else 0
        )

        writer.writerow(
            [
                room.room_id,
                room.name,
                room.room_type,
                count,
                round(hours, 2),
                round(util_rate, 2),
            ]
        )

    return response
