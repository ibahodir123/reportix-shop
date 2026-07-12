from django.urls import path

from .views import ParseProductView

urlpatterns = [
    path("parse-product/", ParseProductView.as_view(), name="voice-parse-product"),
]
