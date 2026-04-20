from django.urls import path
from . import views

urlpatterns = [
    path("", views.tu_login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("book/", views.create_booking_view, name="book_room"),
]
