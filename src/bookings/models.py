from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """
    Custom User Model สำหรับระบบจองห้อง (อ้างอิง FR-AUTH-05)
    ใช้ TU REST API ในการ Verify แล้วค่อยมาสร้าง/อัปเดต User ในระบบนี้
    """

    ROLE_CHOICES = [
        ("Lecturer", "อาจารย์"),
        ("Admin", "เจ้าหน้าที่/แอดมิน"),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="Lecturer")

    def __str__(self):
        return f"{self.username} ({self.role})"


class Room(models.Model):
    """
    ข้อมูลห้องประชุมและห้องเรียน (อ้างอิงหัวข้อ 2.3)
    """

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
    """
    ข้อมูลการจองห้อง (อ้างอิงหัวข้อ 3.2 และ 3.3)
    """

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

    # สำหรับการจองแบบประจำ (FR-BOOK-09 Recurring)
    is_recurring = models.BooleanField(default=False)
    recurring_pattern = models.CharField(
        max_length=50, blank=True, null=True, help_text="เช่น weekly, daily"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Validation พื้นฐาน: เวลาเริ่มต้องมาก่อนเวลาจบ
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("เวลาสิ้นสุดการจองต้องอยู่หลังเวลาเริ่มต้น")

    def __str__(self):
        return f"{self.room.room_id} | {self.user.username} | {self.start_time.strftime('%Y-%m-%d %H:%M')}"
