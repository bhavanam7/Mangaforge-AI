import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectFormPage from './pages/ProjectFormPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import CharacterFormPage from './pages/CharacterFormPage'
import CharactersPage from './pages/CharactersPage'
import StoryChatPage from './pages/StoryChatPage'
import EpisodeFormPage from './pages/EpisodeFormPage'
import EpisodeDetailPage from './pages/EpisodeDetailPage'

export default function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /><Route element={<ProtectedRoute />}><Route path="/dashboard" element={<DashboardPage />} /><Route path="/projects" element={<ProjectsPage />} /><Route path="/projects/new" element={<ProjectFormPage />} /><Route path="/projects/:id" element={<ProjectDetailPage />} /><Route path="/projects/:id/edit" element={<ProjectFormPage />} /><Route path="/projects/:id/characters/new" element={<CharacterFormPage />} /><Route path="/projects/:id/characters/:characterId/edit" element={<CharacterFormPage />} /><Route path="/projects/:id/story" element={<StoryChatPage />} /><Route path="/projects/:id/episodes/new" element={<EpisodeFormPage />} /><Route path="/projects/:id/episodes/:episodeId" element={<EpisodeDetailPage />} /><Route path="/projects/:id/episodes/:episodeId/edit" element={<EpisodeFormPage />} /><Route path="/characters" element={<CharactersPage />} /></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes>
}
