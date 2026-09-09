import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import AuthForm from '../components/AuthForm'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  if (user) return <Navigate to="/dashboard" replace />
  return <AuthPage title="Enter the forge" prompt="New to MangaForge AI?" link="Create an account" to="/register"><>{location.state?.registered && <p className="mt-6 text-sm text-emerald-300">Account created. Please sign in to continue.</p>}<AuthForm mode="login" onSubmit={async (data) => { await login(data); navigate('/dashboard') }} /></></AuthPage>
}

export function AuthPage({ title, prompt, link, to, children }) {
  return <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_15%_20%,_#92400e,_#020617_45%)] px-6"><section className="w-full max-w-md"><p className="mb-10 text-sm font-bold uppercase tracking-[0.3em] text-amber-300">MangaForge AI</p><h1 className="text-4xl font-bold">{title}</h1>{children}<p className="mt-8 text-sm text-slate-400">{prompt} <Link className="text-amber-300 hover:underline" to={to}>{link}</Link></p></section></main>
}
