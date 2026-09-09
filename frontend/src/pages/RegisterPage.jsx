import { Link, Navigate, useNavigate } from 'react-router-dom'
import AuthForm from '../components/AuthForm'
import { useAuth } from '../context/AuthContext'
import { AuthPage } from './LoginPage'

export default function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  if (user) return <Navigate to="/dashboard" replace />
  return <AuthPage title="Build your account" prompt="Already have an account?" link="Sign in" to="/login"><AuthForm mode="register" onSubmit={async (data) => { await register(data); navigate('/login', { replace: true, state: { registered: true } }) }} /></AuthPage>
}
