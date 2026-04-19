from django.urls import path
from . import views

urlpatterns = [
    path("", views.tu_login_view, name="login"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]
