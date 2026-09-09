import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function UserLayout() {
  const { user, logout } = useAuth()
  return <main className="min-h-screen bg-[radial-gradient(circle_at_top_right,_#334155,_#020617_55%)] px-6 py-8"><div className="mx-auto max-w-5xl"><header className="flex items-center justify-between border-b border-slate-700 pb-6"><span className="text-xl font-bold tracking-wide text-amber-300">MangaForge AI</span><nav className="flex items-center gap-5 text-sm text-slate-300"><Link to="/projects" className="hover:text-white">Projects</Link><button onClick={logout} className="hover:text-white">Sign out</button></nav></header><section className="py-20"><p className="mb-3 text-sm uppercase tracking-[0.3em] text-amber-300">{user?.name}</p><h1 className="text-5xl font-bold">Welcome to MangaForge AI</h1><Link to="/projects" className="mt-8 inline-block bg-amber-300 px-5 py-3 font-bold text-slate-950">Manage projects</Link></section></div></main>
}
