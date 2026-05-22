from django.urls import path
from . import views

urlpatterns = [
    path("webhook/line/", views.line_webhook, name="line_webhook"),
]
