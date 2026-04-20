from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db.models import Q


class User(AbstractUser):

    ROLE_CHOICES = [
        ("Lecturer", "อาจารย์"),
        ("Admin", "เจ้าหน้าที่/แอดมิน"),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="Lecturer")

    def __str__(self):
        return f"{self.username} ({self.role})"


class Room(models.Model):

    ROOM_TYPE_CHOICES = [
        ("Meeting", "ห้องประชุม"),
        ("Classroom", "ห้องเรียน"),
    ]

    room_id = models.CharField(
        max_length=20, primary_key=True, help_text="เช่น 406-3, 408-1"
    )
    name = models.CharField(max_length=100, help_text="ชื่อห้อง")
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES)
    capacity = models.IntegerField(help_text="จำนวนที่นั่ง")

    def __str__(self):
        return f"{self.room_id} - {self.name} ({self.capacity} ที่นั่ง)"


class Booking(models.Model):

    STATUS_CHOICES = [
        ("Pending", "รออนุมัติ"),
        ("Approved", "อนุมัติแล้ว"),
        ("Rejected", "ไม่อนุมัติ"),
        ("Cancelled", "ยกเลิกการจอง"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="bookings")
    purpose = models.CharField(max_length=255, help_text="หัวข้อ/วัตถุประสงค์การจอง")

    start_time = models.DateTimeField(help_text="เวลาเริ่มใช้งาน")
    end_time = models.DateTimeField(help_text="เวลาสิ้นสุดการใช้งาน")

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="Pending")

    is_recurring = models.BooleanField(default=False)
    recurring_pattern = models.CharField(
        max_length=50, blank=True, null=True, help_text="เช่น weekly, daily"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("เวลาสิ้นสุดการจองต้องอยู่หลังเวลาเริ่มต้น")

            conflicts = Booking.objects.filter(
                room=self.room,
                status__in=[
                    "Pending",
                    "Approved",
                ],
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )

            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)

            if conflicts.exists():
                raise ValidationError(
                    f"ห้อง {self.room.name} มีการจองในช่วงเวลาดังกล่าวแล้ว (Conflict Detected)"
                )

    def __str__(self):
        return f"{self.room.room_id} | {self.user.username} | {self.start_time.strftime('%Y-%m-%d %H:%M')}"
