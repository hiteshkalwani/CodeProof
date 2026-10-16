from django.http import JsonResponse
from django.urls import include, path

urlpatterns = [
    path("api/", include("snippets.urls")),
    path("health/", lambda request: JsonResponse({"status": "ok"})),
]
