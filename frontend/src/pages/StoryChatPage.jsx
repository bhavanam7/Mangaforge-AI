import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { ErrorState, LoadingState } from '../components/PageState'
import { getProject } from '../api/projects'
import { finalizeStory, getStorySession, sendStoryMessage } from '../api/story'

export default function StoryChatPage() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [session, setSession] = useState(null)
  const [message, setMessage] = useState('')
  const [state, setState] = useState({ loading: true, sending: false, error: '' })

  useEffect(() => {
    Promise.all([getProject(id), getStorySession(id)])
      .then(([projectResponse, sessionResponse]) => { setProject(projectResponse.data); setSession(sessionResponse.data) })
      .catch(() => setState({ loading: false, sending: false, error: 'Unable to load the story workspace.' }))
      .finally(() => setState((current) => ({ ...current, loading: false })))
  }, [id])

  const send = async (event) => {
    event.preventDefault()
    const content = message.trim()
    if (!content || state.sending || session?.status === 'finalized') return
    setState((current) => ({ ...current, sending: true, error: '' }))
    try {
      const response = await sendStoryMessage(id, content)
      setSession((current) => ({ ...current, messages: [...(current?.messages || []), response.data] }))
      setMessage('')
    } catch {
      setState((current) => ({ ...current, error: 'Unable to save your story note.' }))
    } finally {
      setState((current) => ({ ...current, sending: false }))
    }
  }

  const finalize = async () => {
    try { const response = await finalizeStory(id); setSession(response.data) } catch { setState((current) => ({ ...current, error: 'Unable to finalize this story session.' })) }
  }

  if (state.loading) return <AppShell><LoadingState /></AppShell>
  if (state.error && !session) return <AppShell><ErrorState message={state.error} /></AppShell>
  return <AppShell><section className="mx-auto max-w-4xl py-10"><Link to={`/projects/${id}`} className="text-sm text-slate-500 hover:text-violet-300">← Back to {project.title}</Link><div className="mt-6 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.22em] text-violet-300">Story room</p><h1 className="mt-2 text-3xl font-bold text-white">{project.title}</h1></div><span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-violet-200">{session.status}</span></div><div className="studio-card mt-7 p-5 md:p-7"><p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Initial story context</p><p className="mt-3 text-sm leading-7 text-slate-300">{project.description || 'No project description has been added yet.'}</p></div><div className="studio-card mt-5 flex min-h-[420px] flex-col p-4 md:p-6"><div className="mb-5 border-b border-white/[0.08] pb-4"><h2 className="font-bold text-white">Story conversation</h2><p className="mt-1 text-xs text-slate-500">Your notes are saved to this project. AI responses will connect in the next phase.</p></div><div className="flex-1 space-y-4 overflow-y-auto pr-1">{session.messages?.length ? session.messages.map((item) => <div key={item.id} className={`flex ${item.role === 'user' ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.role === 'user' ? 'rounded-br-sm bg-violet-500 text-white' : 'rounded-bl-sm border border-white/[0.1] bg-white/[0.05] text-slate-300'}`}><p className="mb-1 text-[10px] font-bold uppercase tracking-wider opacity-60">{item.role === 'user' ? 'You' : 'AI'}</p>{item.content}</div></div>) : <div className="grid h-full min-h-64 place-items-center text-center text-sm text-slate-500"><div><div className="mx-auto mb-3 text-3xl text-violet-300/50">✦</div><p>Start shaping the story with a note, idea, or direction.</p></div></div>}</div><form onSubmit={send} className="mt-5 flex gap-3 border-t border-white/[0.08] pt-4"><input value={message} onChange={(event) => setMessage(event.target.value)} disabled={session.status === 'finalized' || state.sending} placeholder={session.status === 'finalized' ? 'Story session finalized' : 'Write a story direction...'} className="studio-input" /><button disabled={!message.trim() || state.sending || session.status === 'finalized'} className="primary-button">{state.sending ? 'Saving...' : 'Send'}</button></form>{state.error && <p className="mt-3 text-sm text-rose-300">{state.error}</p>}</div><div className="mt-5 flex justify-end"><button onClick={finalize} disabled={session.status === 'finalized' || !session.messages?.length} className="secondary-button">{session.status === 'finalized' ? 'Story Finalized' : 'Finalize Story'}</button></div></section></AppShell>
}
