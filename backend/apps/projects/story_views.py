from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, StoryMessage, StorySession
from .story_serializers import StoryMessageSerializer, StorySessionSerializer


class ProjectStoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self, request, project_id):
        return get_object_or_404(Project, id=project_id, owner=request.user, is_deleted=False)

    def get_or_create_session(self, request, project_id):
        project = self.get_project(request, project_id)
        session, _ = StorySession.objects.get_or_create(project=project, owner=request.user)
        if project.description and not session.messages.exists():
            StoryMessage.objects.create(
                session=session,
                role=StoryMessage.Role.USER,
                content=project.description,
            )
        return session

    def get(self, request, project_id):
        session = self.get_or_create_session(request, project_id)
        return Response(StorySessionSerializer(session).data)

    def post(self, request, project_id):
        session = self.get_or_create_session(request, project_id)
        if session.status == StorySession.Status.FINALIZED:
            return Response({"detail": "This story session is finalized."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = StoryMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = StoryMessage.objects.create(session=session, role=StoryMessage.Role.USER, content=serializer.validated_data["content"])
        session.save(update_fields=("updated_at",))
        return Response(StoryMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class FinalizeStoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user, is_deleted=False)
        session, _ = StorySession.objects.get_or_create(project=project, owner=request.user)
        session.status = StorySession.Status.FINALIZED
        session.save(update_fields=("status", "updated_at"))
        return Response(StorySessionSerializer(session).data)
