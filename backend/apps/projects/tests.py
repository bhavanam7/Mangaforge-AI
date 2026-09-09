from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.characters.models import Character

from .models import Project, StoryMessage, StorySession


class ProjectAPITests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user("a@example.com", "password-123", name="User A")
        self.user_b = User.objects.create_user("b@example.com", "password-123", name="User B")
        self.client.force_authenticate(self.user_a)

    def project_payload(self, title="A Project"):
        return {"title": title, "description": "A description", "status": "draft"}

    def test_authenticated_user_can_create_project_for_self(self):
        response = self.client.post(reverse("project-list"), self.project_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(id=response.data["id"])
        self.assertEqual(project.owner, self.user_a)

    def test_user_only_lists_and_retrieves_own_projects(self):
        own_project = Project.objects.create(owner=self.user_a, title="Own")
        other_project = Project.objects.create(owner=self.user_b, title="Other")
        response = self.client.get(reverse("project-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [str(own_project.id)])
        self.assertEqual(self.client.get(reverse("project-detail", args=[own_project.id])).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("project-detail", args=[other_project.id])).status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_update_and_soft_delete_own_project(self):
        project = Project.objects.create(owner=self.user_a, title="Before")
        response = self.client.patch(reverse("project-detail", args=[project.id]), {"title": "After"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.delete(reverse("project-detail", args=[project.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        project.refresh_from_db()
        self.assertTrue(project.is_deleted)
        self.assertIsNotNone(project.deleted_at)
        self.assertEqual(self.client.get(reverse("project-list")).data, [])

    def test_user_cannot_update_or_delete_other_users_project(self):
        project = Project.objects.create(owner=self.user_b, title="Other")
        url = reverse("project-detail", args=[project.id])
        self.assertEqual(self.client.patch(url, {"title": "Nope"}, format="json").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_token_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        self.assertEqual(self.client.get(reverse("project-list")).status_code, status.HTTP_401_UNAUTHORIZED)


class CharacterAPITests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user("character-a@example.com", "password-123", name="User A")
        self.user_b = User.objects.create_user("character-b@example.com", "password-123", name="User B")
        self.project = Project.objects.create(owner=self.user_a, title="A Project")
        self.other_project = Project.objects.create(owner=self.user_b, title="B Project")
        self.client.force_authenticate(self.user_a)

    def character_payload(self, name="Aiko"):
        return {"name": name, "surname": "Mori", "age": 18, "hair_color": "Black", "eye_color": "Brown", "importance": "main"}

    def project_characters_url(self, project_id):
        return reverse("project-character-list-create", args=[project_id])

    def test_user_can_create_and_list_character_in_own_project(self):
        response = self.client.post(self.project_characters_url(self.project.id), self.character_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        character = Character.objects.get(id=response.data["id"])
        self.assertEqual(character.project, self.project)
        response = self.client.get(self.project_characters_url(self.project.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_user_can_update_and_soft_delete_character(self):
        character = Character.objects.create(project=self.project, name="Before")
        url = reverse("character-detail", args=[character.id])
        self.assertEqual(self.client.patch(url, {"name": "After"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)
        character.refresh_from_db()
        self.assertTrue(character.is_deleted)
        self.assertIsNotNone(character.deleted_at)
        self.assertEqual(self.client.get(self.project_characters_url(self.project.id)).data, [])

    def test_user_cannot_access_other_users_project_or_characters(self):
        character = Character.objects.create(project=self.project, name="Private")
        self.client.force_authenticate(self.user_b)
        self.assertEqual(self.client.get(self.project_characters_url(self.project.id)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(self.project_characters_url(self.project.id), self.character_payload(), format="json").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("character-detail", args=[character.id])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(reverse("character-detail", args=[character.id]), {"name": "Nope"}, format="json").status_code, status.HTTP_404_NOT_FOUND)

    def test_global_character_list_only_returns_owned_characters(self):
        Character.objects.create(project=self.project, name="Owned")
        Character.objects.create(project=self.other_project, name="Private")
        response = self.client.get(reverse("character-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["name"] for item in response.data], ["Owned"])


class StoryAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("story@example.com", "password-123", name="Story User")
        self.other_user = User.objects.create_user("other-story@example.com", "password-123", name="Other User")
        self.project = Project.objects.create(owner=self.user, title="Story Project", description="A story context.")
        self.client.force_authenticate(self.user)

    def story_url(self):
        return reverse("project-story", args=[self.project.id])

    def test_story_session_persists_user_messages_for_owned_project(self):
        response = self.client.get(self.story_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], StorySession.Status.ACTIVE)
        message = self.client.post(self.story_url(), {"content": "Begin with a quiet garden scene."}, format="json")
        self.assertEqual(message.status_code, status.HTTP_201_CREATED)
        self.assertEqual(message.data["role"], StoryMessage.Role.USER)
        self.assertEqual(StoryMessage.objects.filter(session__project=self.project).count(), 1)

    def test_story_session_can_be_finalized_and_rejects_new_messages(self):
        self.client.post(self.story_url(), {"content": "A first direction."}, format="json")
        finalized = self.client.post(reverse("finalize-story", args=[self.project.id]))
        self.assertEqual(finalized.status_code, status.HTTP_200_OK)
        self.assertEqual(finalized.data["status"], StorySession.Status.FINALIZED)
        self.assertEqual(self.client.post(self.story_url(), {"content": "Another direction."}, format="json").status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_user_cannot_access_story_session(self):
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(self.story_url()).status_code, status.HTTP_404_NOT_FOUND)

