import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import CharacterCard from '../components/CharacterCard'
import ConfirmModal from '../components/ConfirmModal'
import { EmptyState, ErrorState, LoadingState } from '../components/PageState'
import { deleteCharacter, listCharacters } from '../api/characters'
import { deleteProject, getProject } from '../api/projects'

export default function ProjectDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [characters, setCharacters] = useState([])
  const [pendingDelete, setPendingDelete] = useState(null)
  const [state, setState] = useState({ loading: true, error: '' })

  useEffect(() => {
    Promise.all([getProject(id), listCharacters(id)])
      .then(([projectResponse, characterResponse]) => {
        setProject(projectResponse.data)
        setCharacters(characterResponse.data)
      })
      .catch(() => setState({ loading: false, error: 'Unable to load project.' }))
      .finally(() => setState((current) => ({ ...current, loading: false })))
  }, [id])

  const remove = async () => {
    if (pendingDelete.type === 'project') {
      await deleteProject(id)
      navigate('/projects')
    } else {
      await deleteCharacter(pendingDelete.item.id)
      setCharacters((current) => current.filter((character) => character.id !== pendingDelete.item.id))
      setPendingDelete(null)
    }
  }

  if (state.loading) return <AppShell><LoadingState /></AppShell>
  if (state.error) return <AppShell><ErrorState message={state.error} /></AppShell>

  return <AppShell>
    <section className="py-10">
      <Link to="/projects" className="text-sm text-slate-500 hover:text-violet-300">← Back to Projects</Link>
      <div className="studio-card relative mt-5 overflow-hidden p-6 md:p-8">
        <div className="absolute right-0 top-0 h-full w-1/3 bg-[radial-gradient(circle_at_center,rgba(124,58,237,0.18),transparent_68%)]" />
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="flex items-start gap-4">
            <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-violet-500/30 to-indigo-500/10 text-2xl font-black text-violet-200">{project.title.slice(0, 1)}</div>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-bold text-white">{project.title}</h1>
                <span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-200">{project.status}</span>
              </div>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">{project.description || 'No description yet.'}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to={`/projects/${id}/story`} className="primary-button">✦ Start Story</Link>
            <Link to={`/projects/${id}/edit`} className="secondary-button">✎ Edit Project</Link>
            <button onClick={() => setPendingDelete({ type: 'project', item: project })} className="danger-button">Delete</button>
          </div>
        </div>
      </div>
      <div className="mt-8 flex gap-1 border-b border-white/[0.08]">
        <span className="border-b-2 border-violet-400 px-4 py-3 text-sm font-semibold text-violet-200">Overview</span>
        <span className="px-4 py-3 text-sm text-slate-500">Characters <span className="ml-1 text-xs">{characters.length}</span></span>
        <span className="px-4 py-3 text-sm text-slate-600">Episodes</span>
      </div>
      <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_280px]">
        <div>
          <div className="mb-5 flex items-center justify-between">
            <div><p className="text-xs uppercase tracking-[0.2em] text-violet-300">Cast library</p><h2 className="mt-1 text-2xl font-bold text-white">Characters</h2></div>
            <Link to={`/projects/${id}/characters/new`} className="primary-button">＋ Add Character</Link>
          </div>
          {characters.length === 0 ? <EmptyState message="No characters yet. Add the first person to this story." /> : <div className="grid gap-5 md:grid-cols-2">{characters.map((character) => <CharacterCard key={character.id} character={character} projectId={id} onDelete={(item) => setPendingDelete({ type: 'character', item })} />)}</div>}
        </div>
        <aside className="studio-card h-fit p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Project information</p>
          <dl className="mt-5 space-y-4 text-sm">
            <div><dt className="text-slate-500">Characters</dt><dd className="mt-1 text-xl font-bold text-white">{characters.length}</dd></div>
            <div><dt className="text-slate-500">Episodes</dt><dd className="mt-1 text-xl font-bold text-slate-600">Not available yet</dd></div>
            <div><dt className="text-slate-500">Status</dt><dd className="mt-1 capitalize text-slate-300">{project.status}</dd></div>
            <div><dt className="text-slate-500">Last updated</dt><dd className="mt-1 text-slate-300">{new Date(project.updated_at).toLocaleDateString()}</dd></div>
          </dl>
        </aside>
      </div>
    </section>
    {pendingDelete && <ConfirmModal title={`Delete “${pendingDelete.item.title || pendingDelete.item.name}”?`} message="This item will disappear from your workspace. The record remains soft-deleted for data safety." onClose={() => setPendingDelete(null)} onConfirm={remove} />}
  </AppShell>
}
