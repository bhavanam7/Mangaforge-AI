from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import Episode
from .serializers import EpisodeSerializer


def owned_project(user, project_id):
    return get_object_or_404(Project, id=project_id, owner=user, is_deleted=False)


class EpisodeViewSet(viewsets.ModelViewSet):
    serializer_class = EpisodeSerializer

    def get_queryset(self):
        return Episode.objects.filter(project__owner=self.request.user, project__is_deleted=False, is_deleted=False)

    def destroy(self, request, *args, **kwargs):
        episode = self.get_object()
        episode.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectEpisodeListCreateView(APIView):
    def get(self, request, project_id):
        project = owned_project(request.user, project_id)
        episodes = Episode.objects.filter(project=project, is_deleted=False)
        return Response(EpisodeSerializer(episodes, many=True).data)

    def post(self, request, project_id):
        project = owned_project(request.user, project_id)
        serializer = EpisodeSerializer(data=request.data, context={"project": project})
        serializer.is_valid(raise_exception=True)
        episode = serializer.save(project=project)
        return Response(EpisodeSerializer(episode).data, status=status.HTTP_201_CREATED)
