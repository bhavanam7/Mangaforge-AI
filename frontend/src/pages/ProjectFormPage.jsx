import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { ErrorState } from '../components/PageState'
import { createProject, getProject, updateProject } from '../api/projects'

const emptyProject = { title: '', description: '', status: 'draft', cover_image: null }

export default function ProjectFormPage() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyProject)
  const [state, setState] = useState({ loading: editing, saving: false, error: '' })

  useEffect(() => { if (editing) getProject(id).then((response) => setForm(response.data)).catch(() => setState({ loading: false, saving: false, error: 'Unable to load project.' })).finally(() => setState((current) => ({ ...current, loading: false }))) }, [editing, id])
  const update = (event) => setForm({ ...form, [event.target.name]: event.target.type === 'file' ? event.target.files[0] : event.target.value })
  const submit = async (event) => { event.preventDefault(); setState({ ...state, saving: true, error: '' }); const payload = new FormData(); Object.entries(form).forEach(([key, value]) => { if (value !== null && value !== '') payload.append(key, value) }); try { const response = editing ? await updateProject(id, payload) : await createProject(payload); navigate(`/projects/${response.data.id}`) } catch (error) { setState({ ...state, saving: false, error: Object.values(error.response?.data || {}).flat().join(' ') || 'Unable to save project.' }) } }
  if (state.loading) return <AppShell><p className="py-16 text-slate-400">Loading...</p></AppShell>
  return <AppShell><section className="mx-auto max-w-3xl py-10"><Link to={editing ? `/projects/${id}` : '/projects'} className="text-sm text-slate-500 hover:text-violet-300">← Back</Link><div className="mt-6"><p className="text-xs font-bold uppercase tracking-[0.22em] text-violet-300">Project setup</p><h1 className="mt-2 text-3xl font-bold text-white md:text-4xl">{editing ? 'Edit project' : 'Create New Project'}</h1><p className="mt-3 text-sm text-slate-400">Give your next story a home. You can refine these details later.</p></div>{state.error && <div className="mt-6"><ErrorState message={state.error} /></div>}<form onSubmit={submit} className="studio-card mt-8 p-6 md:p-8"><div className="grid gap-6 md:grid-cols-2"><label className="md:col-span-2"><span className="studio-label">Project title</span><input required name="title" value={form.title} onChange={update} placeholder="e.g. The Lantern District" className="studio-input" /></label><label className="md:col-span-2"><span className="studio-label">Description</span><textarea name="description" value={form.description} onChange={update} rows="5" placeholder="What is this story about?" className="studio-input resize-y" /><span className="mt-2 block text-xs text-slate-500">A short premise helps you find the project quickly later.</span></label><label><span className="studio-label">Status</span><select name="status" value={form.status} onChange={update} className="studio-input"><option value="draft">Draft</option><option value="active">Active</option><option value="completed">Completed</option></select></label><label><span className="studio-label">Cover image</span><span className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-white/[0.15] px-4 py-3 text-sm text-slate-400 hover:border-violet-400/50"><span className="text-lg text-violet-300">＋</span><span>{form.cover_image?.name || 'Choose an image'}</span><input type="file" accept="image/*" name="cover_image" onChange={update} className="hidden" /></span></label></div><div className="mt-8 flex flex-wrap justify-end gap-3 border-t border-white/[0.08] pt-6"><Link to={editing ? `/projects/${id}` : '/projects'} className="secondary-button">Cancel</Link><button disabled={state.saving} className="primary-button">{state.saving ? 'Saving...' : editing ? 'Save changes' : 'Create Project'}</button></div></form></section></AppShell>
}
