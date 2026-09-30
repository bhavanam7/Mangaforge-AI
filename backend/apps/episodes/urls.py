from django.urls import path

from .views import EpisodeViewSet


episode_detail = EpisodeViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("<uuid:pk>/", episode_detail, name="episode-detail"),
]
