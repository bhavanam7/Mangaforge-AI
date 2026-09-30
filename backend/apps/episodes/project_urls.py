from django.urls import path

from .views import ProjectEpisodeListCreateView


urlpatterns = [
    path("", ProjectEpisodeListCreateView.as_view(), name="project-episode-list-create"),
]
