import { useState } from 'react'

const getErrorMessage = (requestError) => {
  const responseData = requestError.response?.data
  if (responseData?.detail) return responseData.detail
  if (responseData && typeof responseData === 'object') {
    return Object.values(responseData).flat().join(' ')
  }
  return 'Unable to complete request.'
}

export default function AuthForm({ mode, onSubmit }) {
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const update = (event) => setForm({ ...form, [event.target.name]: event.target.value })
  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onSubmit(form)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-8 space-y-5">
      {mode === 'register' && <input required name="name" placeholder="Name" value={form.name} onChange={update} className="w-full border-b border-slate-600 bg-transparent p-3 outline-none focus:border-amber-300" />}
      <input required type="email" name="email" placeholder="Email" value={form.email} onChange={update} className="w-full border-b border-slate-600 bg-transparent p-3 outline-none focus:border-amber-300" />
      <input required minLength="8" type="password" name="password" placeholder="Password" value={form.password} onChange={update} className="w-full border-b border-slate-600 bg-transparent p-3 outline-none focus:border-amber-300" />
      {error && <p className="text-sm text-rose-300">{error}</p>}
      <button disabled={loading} className="w-full bg-amber-300 px-4 py-3 font-bold text-slate-950 transition hover:bg-amber-200 disabled:opacity-50">{loading ? 'Please wait...' : mode === 'register' ? 'Create account' : 'Sign in'}</button>
    </form>
  )
}
