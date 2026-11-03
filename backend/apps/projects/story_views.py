import sys
from pathlib import Path

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, StoryMessage, StorySession
from .story_serializers import StoryMessageSerializer, StorySessionSerializer

# # Add ai_pipeline directory to sys.path if not already present
# AI_PIPELINE_PATH = Path("/home/cis/Desktop/Swayam/Projects/Manga/Mangaforge-AI/ai_pipeline")
# if str(AI_PIPELINE_PATH) not in sys.path:
#     sys.path.append(str(AI_PIPELINE_PATH))

# Add project root (Mangaforge-AI) to sys.path
# Add Mangaforge-AI (parent of ai_pipeline) to sys.path
AI_PIPELINE_DIR = Path("/home/cis/Desktop/Swayam/Projects/Manga/Mangaforge-AI/ai_pipeline")

if str(AI_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_DIR))

try:
    from main import run_pipeline
except ImportError as e:
    print(f"Import failed: {e}")
    def run_pipeline(user_content, stage, enriched_content, json_output, action="chat",
                     scope=None, target_id=None):
        return f"Fallback response for stage '{stage}'", stage, enriched_content, json_output


def _request_scope(request):
    """Read the optional enhancement-hub context markers from the payload.

    The React chat box sends `{ content, scope, target_id }` once the session is
    in the enhancement hub (see
    `ai_pipeline/dynamic_multi_entity_enhancement_workflow.md`, Section 2).
    `scope` is restricted to the values the orchestrator understands so a
    malformed payload falls back to the pipeline's own intent routing.
    """
    scope = request.data.get("scope")
    if isinstance(scope, str):
        scope = scope.strip().lower()
    else:
        scope = None
    if scope not in ("character", "background", "scene", "story", "auto"):
        scope = None

    target_id = request.data.get("target_id")
    if target_id is not None and not isinstance(target_id, (str, int)):
        target_id = None
    elif target_id is not None:
        target_id = str(target_id).strip() or None

    return scope, target_id


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
        
        user_action = request.data.get("action", "chat")  # e.g., "chat" or "finalize_stage"
        user_scope, target_id = _request_scope(request)
        raw_content = request.data.get("content")
        user_content = raw_content.strip() if isinstance(raw_content, str) else ""

        # An enhancement-hub entity selection may arrive without text: the user
        # only clicked an entity to load its summary. Every other turn still
        # needs a message, so keep the serializer's validation for those.
        if not user_content and not (user_scope and target_id):
            serializer = StoryMessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_content = serializer.validated_data["content"]

        print(f"\n[CHATBOT RECEIVE] Project {project_id} | Stage: {session.stage} - User: {user_content}\n", flush=True)

        # 1. Save incoming user message (empty for a bare entity selection)
        if user_content:
            StoryMessage.objects.create(
                session=session,
                role=StoryMessage.Role.USER,
                content=user_content
            )

        # 2. Invoke AI Pipeline passing user_content, current stage, enriched_content, and json_output
        ai_reply, new_stage, new_enriched_content, new_json_output = run_pipeline(
            user_content=user_content,
            stage=session.stage,
            enriched_content=session.enriched_content,
            json_output=session.json_output,
            action=user_action,
            scope=user_scope,
            target_id=target_id,
        )

        # 3. Save AI Assistant response
        StoryMessage.objects.create(
            session=session,
            role=StoryMessage.Role.ASSISTANT,
            content=ai_reply
        )

        # 4. Save updated state, enriched_content, and json_output in DB
        session.stage = new_stage
        session.enriched_content = new_enriched_content
        session.json_output = new_json_output
        session.save()

        # 5. Return updated session data to sync with frontend
        return Response(StorySessionSerializer(session).data, status=status.HTTP_201_CREATED)


class FinalizeStoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user, is_deleted=False)
        session, _ = StorySession.objects.get_or_create(project=project, owner=request.user)

        # Finalising the draft is a pipeline step (Phase 3 extraction), not a flag
        # flip: the master JSON has to be rebuilt from the *current*
        # enriched_content, otherwise the structured state keeps describing the
        # previous revision of the story. The session stays ACTIVE so the user can
        # keep working in the Phase 4 enhancement hub afterwards.
        if session.stage != StorySession.Stage.ENRICHED_CONTENT:
            return Response(StorySessionSerializer(session).data)

        print(f"\n[FINALIZE] Project {project_id} | Stage: {session.stage}\n", flush=True)

        ai_reply, new_stage, new_enriched_content, new_json_output = run_pipeline(
            user_content="finalize story draft",
            stage=session.stage,
            enriched_content=session.enriched_content,
            json_output=session.json_output,
            action="finalize_stage",
            scope=None,
            target_id=None,
        )

        StoryMessage.objects.create(
            session=session,
            role=StoryMessage.Role.ASSISTANT,
            content=ai_reply,
        )

        session.stage = new_stage
        session.enriched_content = new_enriched_content
        session.json_output = new_json_output
        session.save()

        return Response(StorySessionSerializer(session).data)