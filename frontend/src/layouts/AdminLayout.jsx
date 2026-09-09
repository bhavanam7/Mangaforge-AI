import { useAuth } from '../context/AuthContext'

export default function AdminLayout() {
  const { logout } = useAuth()
  return <main className="min-h-screen bg-slate-950 px-6 py-8"><div className="mx-auto max-w-5xl"><header className="flex justify-between border-b border-slate-700 pb-6"><span className="font-bold text-amber-300">MangaForge AI / Admin</span><button onClick={logout} className="text-sm text-slate-300 hover:text-white">Sign out</button></header><h1 className="py-20 text-4xl font-bold">Admin Dashboard</h1></div></main>
}
