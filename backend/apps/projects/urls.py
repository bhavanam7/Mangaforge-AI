from django.urls import path

from .views import ProjectViewSet
from .story_views import FinalizeStoryView, ProjectStoryView


project_list = ProjectViewSet.as_view({"get": "list", "post": "create"})
project_detail = ProjectViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("", project_list, name="project-list"),
    path("<uuid:pk>/", project_detail, name="project-detail"),
    path("<uuid:project_id>/story/", ProjectStoryView.as_view(), name="project-story"),
    path("<uuid:project_id>/story/finalize/", FinalizeStoryView.as_view(), name="finalize-story"),
]
