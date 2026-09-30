import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { ErrorState, LoadingState } from '../components/PageState'
import { createEpisode, getEpisode, updateEpisode } from '../api/episodes'

const initialForm = { title: '', summary: '', episode_number: 1, status: 'draft' }

export default function EpisodeFormPage() {
  const { id: projectId, episodeId } = useParams()
  const editing = Boolean(episodeId)
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [state, setState] = useState({ loading: editing, saving: false, error: '' })

  useEffect(() => { if (editing) getEpisode(episodeId).then((response) => setForm(response.data)).catch(() => setState({ loading: false, saving: false, error: 'Unable to load episode.' })).finally(() => setState((current) => ({ ...current, loading: false }))) }, [editing, episodeId])
  const update = (event) => setForm({ ...form, [event.target.name]: event.target.value })
  const submit = async (event) => { event.preventDefault(); setState({ ...state, saving: true, error: '' }); try { const response = editing ? await updateEpisode(episodeId, form) : await createEpisode(projectId, form); navigate(`/projects/${projectId}/episodes/${response.data.id}`) } catch (error) { setState({ ...state, saving: false, error: Object.values(error.response?.data || {}).flat().join(' ') || 'Unable to save episode.' }) } }
  if (state.loading) return <AppShell><LoadingState /></AppShell>
  return <AppShell><section className="mx-auto max-w-3xl py-10"><Link to={`/projects/${projectId}`} className="text-sm text-slate-500 hover:text-violet-300">← Back to project</Link><div className="mt-6"><p className="text-xs font-bold uppercase tracking-[0.22em] text-violet-300">Episode management</p><h1 className="mt-2 text-3xl font-bold text-white md:text-4xl">{editing ? 'Edit Episode' : 'Create Episode'}</h1><p className="mt-3 text-sm text-slate-400">Add the next chapter to this project. AI story generation can be connected later.</p></div>{state.error && <div className="mt-6"><ErrorState message={state.error} /></div>}<form onSubmit={submit} className="studio-card mt-8 space-y-6 p-6 md:p-8"><div className="grid gap-5 md:grid-cols-[140px_1fr]"><label><span className="studio-label">Number</span><input required min="1" type="number" name="episode_number" value={form.episode_number} onChange={update} className="studio-input" /></label><label><span className="studio-label">Title</span><input required name="title" value={form.title} onChange={update} placeholder="e.g. The Garden Promise" className="studio-input" /></label></div><label className="block"><span className="studio-label">Description / Summary</span><textarea name="summary" value={form.summary} onChange={update} rows="6" placeholder="What happens in this episode?" className="studio-input resize-y" /></label><label className="block"><span className="studio-label">Status</span><select name="status" value={form.status} onChange={update} className="studio-input"><option value="draft">Draft</option><option value="active">Active</option><option value="completed">Completed</option></select></label><div className="flex justify-end gap-3 border-t border-white/[0.08] pt-6"><Link to={`/projects/${projectId}`} className="secondary-button">Cancel</Link><button disabled={state.saving} className="primary-button">{state.saving ? 'Saving...' : editing ? 'Save changes' : 'Create Episode'}</button></div></form></section></AppShell>
}