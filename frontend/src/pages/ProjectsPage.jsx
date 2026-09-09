import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import { EmptyState, ErrorState, LoadingState } from '../components/PageState'
import { deleteProject, listProjects } from '../api/projects'
import ProjectCard from '../components/ProjectCard'
import ConfirmModal from '../components/ConfirmModal'

export default function ProjectsPage() {
  const [projects, setProjects] = useState([])
  const [state, setState] = useState({ loading: true, error: '' })
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [pendingDelete, setPendingDelete] = useState(null)

  useEffect(() => {
    listProjects().then((response) => setProjects(response.data)).catch(() => setState({ loading: false, error: 'Unable to load projects.' })).finally(() => setState((current) => ({ ...current, loading: false })))
  }, [])

  const remove = async () => {
    await deleteProject(pendingDelete.id)
    setProjects((current) => current.filter((project) => project.id !== pendingDelete.id))
    setPendingDelete(null)
  }
  const visibleProjects = projects.filter((project) => project.title.toLowerCase().includes(query.toLowerCase()) && (status === 'all' || project.status === status))

  return <AppShell><section className="py-10"><div className="mb-8 flex flex-wrap items-end justify-between gap-5"><div><p className="text-xs font-bold uppercase tracking-[0.22em] text-violet-300">Your workspace</p><h1 className="mt-2 text-3xl font-bold text-white md:text-4xl">Projects</h1><p className="mt-2 text-sm text-slate-400">Build the worlds your stories will live in.</p></div><Link to="/projects/new" className="primary-button">＋ Create Project</Link></div><div className="studio-card mb-7 flex flex-col gap-3 p-3 sm:flex-row"><div className="relative flex-1"><span className="pointer-events-none absolute left-4 top-3 text-slate-500">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your projects" className="studio-input pl-10" /></div><select value={status} onChange={(event) => setStatus(event.target.value)} className="studio-input sm:w-44"><option value="all">All statuses</option><option value="draft">Draft</option><option value="active">Active</option><option value="completed">Completed</option></select></div>{state.loading ? <LoadingState /> : state.error ? <ErrorState message={state.error} /> : projects.length === 0 ? <EmptyState message="No projects yet. Create your first manga project and start building your story." /> : visibleProjects.length === 0 ? <EmptyState message="No projects match your search." /> : <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{visibleProjects.map((project) => <ProjectCard key={project.id} project={project} onDelete={setPendingDelete} />)}</div>}</section>{pendingDelete && <ConfirmModal title={`Delete “${pendingDelete.title}”?`} message="This project will be removed from your workspace. Its data is safely soft-deleted and can be restored later by an administrator." onClose={() => setPendingDelete(null)} onConfirm={remove} />}</AppShell>
}
