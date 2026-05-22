from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Room, Booking


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ["username", "first_name", "role", "line_user_id", "is_staff"]

    fieldsets = UserAdmin.fieldsets + (
        ("ข้อมูลเพิ่มเติม", {"fields": ("role", "line_user_id")}),
    )


admin.site.register(User, CustomUserAdmin)
admin.site.register(Room)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["room", "user", "purpose_type", "start_time", "status"]
    list_filter = ["status", "purpose_type", "room"]
