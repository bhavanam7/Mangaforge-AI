import { createContext, useContext, useEffect, useState } from 'react'
import * as authApi from '../api/auth'

const AuthContext = createContext(null)
const ACCESS_KEY = 'mangaforge_access_token'
const REFRESH_KEY = 'mangaforge_refresh_token'
const USER_KEY = 'mangaforge_user'

const readUser = () => {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY))
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readUser)

  useEffect(() => {
    const handleExpiredSession = () => setUser(null)
    window.addEventListener('mangaforge:auth-expired', handleExpiredSession)
    return () => window.removeEventListener('mangaforge:auth-expired', handleExpiredSession)
  }, [])

  const saveSession = (data) => {
    sessionStorage.setItem(ACCESS_KEY, data.access)
    sessionStorage.setItem(REFRESH_KEY, data.refresh)
    sessionStorage.setItem(USER_KEY, JSON.stringify(data.user))
    setUser(data.user)
  }

  const login = async (payload) => saveSession((await authApi.login(payload)).data)
  const register = async (payload) => authApi.register(payload)
  const logout = async () => {
    const refreshToken = sessionStorage.getItem(REFRESH_KEY)
    try {
      if (refreshToken) await authApi.logout(refreshToken)
    } finally {
      sessionStorage.removeItem(ACCESS_KEY)
      sessionStorage.removeItem(REFRESH_KEY)
      sessionStorage.removeItem(USER_KEY)
      setUser(null)
    }
  }

  return <AuthContext.Provider value={{ user, login, register, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
