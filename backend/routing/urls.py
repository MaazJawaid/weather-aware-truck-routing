from django.urls import path

from routing.views import AnalyzeView, HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("analyze", AnalyzeView.as_view(), name="analyze"),
]
