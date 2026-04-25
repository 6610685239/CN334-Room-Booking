from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path(
        "approve/<int:booking_id>/",
        views.update_status,
        {"new_status": "Approved"},
        name="approve_booking",
    ),
    path(
        "reject/<int:booking_id>/",
        views.update_status,
        {"new_status": "Rejected"},
        name="reject_booking",
    ),
    path("cancel/<int:booking_id>/", views.cancel_booking, name="cancel_booking"),
    path("rooms/", views.manage_rooms, name="manage_rooms"),
    path("rooms/save/", views.save_room, name="save_room"),
]