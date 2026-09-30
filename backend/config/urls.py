from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/health/", include("apps.health.urls")),
    path("api/projects/", include("apps.projects.urls")),
    path("api/projects/<uuid:project_id>/characters/", include("apps.characters.project_urls")),
    path("api/projects/<uuid:project_id>/episodes/", include("apps.episodes.project_urls")),
    path("api/characters/", include("apps.characters.urls")),
    path("api/episodes/", include("apps.episodes.urls")),
]
