from django.urls import path

from .views import ProjectCharacterListCreateView


urlpatterns = [
    path("", ProjectCharacterListCreateView.as_view(), name="project-character-list-create"),
]
