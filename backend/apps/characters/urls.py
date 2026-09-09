from django.urls import path

from .views import CharacterListView, CharacterViewSet


character_detail = CharacterViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("", CharacterListView.as_view(), name="character-list"),
    path("<uuid:pk>/", character_detail, name="character-detail"),
]
