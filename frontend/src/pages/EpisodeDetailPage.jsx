import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import ConfirmModal from '../components/ConfirmModal'
import { ErrorState, LoadingState } from '../components/PageState'
import { deleteEpisode, getEpisode } from '../api/episodes'

export default function EpisodeDetailPage() {
  const { id: projectId, episodeId } = useParams()
  const navigate = useNavigate()
  const [episode, setEpisode] = useState(null)
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)
  useEffect(() => { getEpisode(episodeId).then((response) => setEpisode(response.data)).catch(() => setError('Unable to load episode.')) }, [episodeId])
  const remove = async () => { await deleteEpisode(episodeId); navigate(`/projects/${projectId}`) }
  if (error) return <AppShell><ErrorState message={error} /></AppShell>
  if (!episode) return <AppShell><LoadingState /></AppShell>
  return <AppShell><section className="mx-auto max-w-4xl py-10"><Link to={`/projects/${projectId}`} className="text-sm text-slate-500 hover:text-violet-300">← Back to project</Link><div className="studio-card mt-6 p-6 md:p-8"><div className="flex flex-wrap items-start justify-between gap-5"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-violet-300">Episode {episode.episode_number}</p><h1 className="mt-2 text-3xl font-bold text-white">{episode.title}</h1><span className="mt-4 inline-block rounded-full border border-violet-300/20 bg-violet-300/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-violet-200">{episode.status}</span></div><div className="flex gap-3"><Link to={`/projects/${projectId}/episodes/${episodeId}/edit`} className="secondary-button">✎ Edit</Link><button onClick={() => setConfirming(true)} className="danger-button">Delete</button></div></div><div className="mt-8 border-t border-white/[0.08] pt-6"><p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Description / Summary</p><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-300">{episode.summary || 'No summary has been added yet.'}</p></div></div></section>{confirming && <ConfirmModal title={`Delete “${episode.title}”?`} message="This episode will be removed from the visible project workspace. The record remains soft-deleted for data safety." onClose={() => setConfirming(false)} onConfirm={remove} />}</AppShell>
}