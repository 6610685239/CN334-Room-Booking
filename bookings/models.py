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
    is_active = models.BooleanField(default=True, verbose_name="เปิดใช้งาน")

    def __str__(self):
        return f"{self.room_id} - {self.name} ({self.capacity} ที่นั่ง)"


class Booking(models.Model):
    PURPOSE_CHOICES = [
        ("Teaching", "สอนปกติ/ชดเชย/เสริม"),
        ("Training", "จัดอบรม/จัดติว"),
    ]

    PROGRAM_CHOICES = [
        ("Bachelor", "ปริญญาตรีภาคปกติ"),
        ("Master", "ปริญญาโท"),
        ("TEP_TEPE", "TEP-TEPE"),
        ("TU_PINE", "TU-PINE"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)

    purpose_type = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default="Teaching"
    )

    course_code = models.CharField(max_length=20, blank=True, null=True)
    course_name = models.CharField(max_length=100, blank=True, null=True)
    program = models.CharField(
        max_length=20, choices=PROGRAM_CHOICES, blank=True, null=True
    )

    training_topic = models.CharField(max_length=200, blank=True, null=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")

        if self.purpose_type == "Teaching":
            if not self.course_code or not self.course_name or not self.program:
                raise ValidationError(
                    "สำหรับการสอน: กรุณาระบุรหัสวิชา ชื่อวิชา และหลักสูตรให้ครบถ้วน"
                )
        elif self.purpose_type == "Training":
            if not self.training_topic:
                raise ValidationError("สำหรับการจัดอบรม/ติว: กรุณาระบุชื่อเรื่อง")

        if self.start_time and self.end_time and self.room:
            conflicts = Booking.objects.filter(
                room=self.room,
                status__in=["Pending", "Approved"],
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )

            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)

            if conflicts.exists():
                raise ValidationError(
                    f"ห้อง {self.room.name} ถูกจองแล้วในช่วงเวลาดังกล่าว กรุณาเลือกเวลาอื่น"
                )

    def __str__(self):
        return f"{self.room.room_id} - {self.user.username}"
