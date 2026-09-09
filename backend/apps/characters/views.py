from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import Character
from .serializers import CharacterSerializer


def owned_project(user, project_id):
    try:
        return Project.objects.get(id=project_id, owner=user, is_deleted=False)
    except Project.DoesNotExist as error:
        raise NotFound("Project not found.") from error


class CharacterViewSet(viewsets.ModelViewSet):
    serializer_class = CharacterSerializer

    def get_queryset(self):
        return Character.objects.filter(project__owner=self.request.user, project__is_deleted=False, is_deleted=False)

    def destroy(self, request, *args, **kwargs):
        character = self.get_object()
        character.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CharacterListView(APIView):
    def get(self, request):
        characters = Character.objects.filter(
            project__owner=request.user,
            project__is_deleted=False,
            is_deleted=False,
        ).select_related("project")
        data = CharacterSerializer(characters, many=True).data
        for item, character in zip(data, characters):
            item["project_title"] = character.project.title
        return Response(data)


class ProjectCharacterListCreateView(APIView):
    def get(self, request, project_id):
        project = owned_project(request.user, project_id)
        characters = Character.objects.filter(project=project, is_deleted=False)
        return Response(CharacterSerializer(characters, many=True).data)

    def post(self, request, project_id):
        project = owned_project(request.user, project_id)
        serializer = CharacterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        character = serializer.save(project=project)
        return Response(CharacterSerializer(character).data, status=status.HTTP_201_CREATED)
