from django.urls import path
from . import views

urlpatterns = [
    path("", views.report_dashboard, name="report_dashboard"),
    path("export/csv/", views.export_report_csv, name="export_report_csv"),
]
