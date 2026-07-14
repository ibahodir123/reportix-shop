from django.urls import path

from .views import AssistantMessageView

urlpatterns = [
    path("message/", AssistantMessageView.as_view(), name="assistant-message"),
]
