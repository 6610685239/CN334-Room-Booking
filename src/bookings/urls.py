from django.urls import path
from . import views

urlpatterns = [
    path("", views.tu_login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("book/", views.create_booking_view, name="book_room"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("api/booked-slots/", views.api_get_booked_slots, name="api_booked_slots"),
]
