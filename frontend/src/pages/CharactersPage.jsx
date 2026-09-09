import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import CharacterCard from '../components/CharacterCard'
import ConfirmModal from '../components/ConfirmModal'
import { EmptyState, ErrorState, LoadingState } from '../components/PageState'
import { deleteCharacter, listAllCharacters } from '../api/characters'
import { listProjects } from '../api/projects'

export default function CharactersPage() {
  const navigate = useNavigate()
  const [characters, setCharacters] = useState([])
  const [projects, setProjects] = useState([])
  const [query, setQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedProject, setSelectedProject] = useState('')
  const [pendingDelete, setPendingDelete] = useState(null)
  const [state, setState] = useState({ loading: true, error: '' })

  useEffect(() => {
    Promise.all([listAllCharacters(), listProjects()])
      .then(([characterResponse, projectResponse]) => {
        setCharacters(characterResponse.data)
        setProjects(projectResponse.data)
      })
      .catch(() => setState({ loading: false, error: 'Unable to load characters.' }))
      .finally(() => setState((current) => ({ ...current, loading: false })))
  }, [])

  const openCreate = () => {
    if (projects.length === 1) navigate(`/projects/${projects[0].id}/characters/new`)
    else setShowCreate(true)
  }

  const continueCreate = () => {
    if (selectedProject) navigate(`/projects/${selectedProject}/characters/new`)
  }

  const remove = async () => {
    await deleteCharacter(pendingDelete.id)
    setCharacters((current) => current.filter((character) => character.id !== pendingDelete.id))
    setPendingDelete(null)
  }

  const visible = characters.filter((character) => `${character.name} ${character.surname} ${character.project_title}`.toLowerCase().includes(query.toLowerCase()))

  return <AppShell><section className="py-10"><div className="mb-8 flex flex-wrap items-end justify-between gap-5"><div><p className="text-xs font-bold uppercase tracking-[0.22em] text-violet-300">Cast library</p><h1 className="mt-2 text-3xl font-bold text-white md:text-4xl">Characters</h1><p className="mt-2 text-sm text-slate-400">Every story starts with someone worth following.</p></div><button onClick={openCreate} className="primary-button">＋ Create Character</button></div><div className="studio-card mb-7 p-3"><div className="relative"><span className="pointer-events-none absolute left-4 top-3 text-slate-500">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search characters or projects" className="studio-input pl-10" /></div></div>{state.loading ? <LoadingState /> : state.error ? <ErrorState message={state.error} /> : characters.length === 0 ? <EmptyState message="No characters yet. Create one inside a project to start your cast library." /> : visible.length === 0 ? <EmptyState message="No characters match your search." /> : <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{visible.map((character) => <div key={character.id}><CharacterCard character={character} projectId={character.project} onDelete={setPendingDelete} /><p className="mt-2 px-1 text-xs text-slate-500">From {character.project_title}</p></div>)}</div>}</section>{showCreate && <div className="fixed inset-0 z-40 grid place-items-center bg-black/70 px-5 backdrop-blur-sm"><div className="studio-card w-full max-w-md p-6"><p className="text-xs font-bold uppercase tracking-[0.2em] text-violet-300">New character</p><h2 className="mt-2 text-2xl font-bold text-white">Choose a project</h2><p className="mt-2 text-sm leading-6 text-slate-400">Every character belongs to a project. Select where this character should live.</p><select value={selectedProject} onChange={(event) => setSelectedProject(event.target.value)} className="studio-input mt-6"><option value="">Select a project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select><div className="mt-6 flex justify-end gap-3"><button onClick={() => setShowCreate(false)} className="secondary-button">Cancel</button><button disabled={!selectedProject} onClick={continueCreate} className="primary-button">Continue →</button></div></div></div>}{pendingDelete && <ConfirmModal title={`Delete “${pendingDelete.name}”?`} message="This character will disappear from your library. The record remains soft-deleted for data safety." onClose={() => setPendingDelete(null)} onConfirm={remove} />}</AppShell>
}
