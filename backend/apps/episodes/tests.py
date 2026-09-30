from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project

from .models import Episode


class EpisodeAPITests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user("episode-a@example.com", "password-123", name="User A")
        self.user_b = User.objects.create_user("episode-b@example.com", "password-123", name="User B")
        self.project = Project.objects.create(owner=self.user_a, title="A Project")
        self.other_project = Project.objects.create(owner=self.user_b, title="B Project")
        self.client.force_authenticate(self.user_a)

    def list_url(self, project_id=None):
        return reverse("project-episode-list-create", args=[project_id or self.project.id])

    def payload(self, title="Opening chapter", number=1):
        return {"title": title, "summary": "The story begins.", "episode_number": number, "status": "draft"}

    def test_user_can_create_and_list_own_project_episodes(self):
        response = self.client.post(self.list_url(), self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        episode = Episode.objects.get(id=response.data["id"])
        self.assertEqual(episode.project, self.project)
        self.assertEqual(self.client.get(self.list_url()).status_code, status.HTTP_200_OK)

    def test_user_can_update_and_soft_delete_episode(self):
        episode = Episode.objects.create(project=self.project, title="Before", episode_number=1)
        detail_url = reverse("episode-detail", args=[episode.id])
        self.assertEqual(self.client.patch(detail_url, {"title": "After"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_204_NO_CONTENT)
        episode.refresh_from_db()
        self.assertTrue(episode.is_deleted)
        self.assertIsNotNone(episode.deleted_at)
        self.assertEqual(self.client.get(self.list_url()).data, [])

    def test_user_cannot_access_other_users_episodes_or_create_in_other_project(self):
        episode = Episode.objects.create(project=self.other_project, title="Private", episode_number=1)
        self.assertEqual(self.client.get(self.list_url(self.other_project.id)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(self.list_url(self.other_project.id), self.payload(), format="json").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("episode-detail", args=[episode.id])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(reverse("episode-detail", args=[episode.id]), {"title": "Nope"}, format="json").status_code, status.HTTP_404_NOT_FOUND)

    def test_episode_numbers_are_unique_for_active_episodes_in_project(self):
        Episode.objects.create(project=self.project, title="First", episode_number=1)
        response = self.client.post(self.list_url(), self.payload(title="Duplicate"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
