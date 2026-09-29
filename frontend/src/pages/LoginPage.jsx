import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'

const LoginPage = () => {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(form.email, form.password)
      navigate(data.role === 'farmer' ? '/farmer' : data.role === 'buyer' ? '/buyer' : '/admin')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : detail?.message || err.response?.data?.message || 'Login failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-gradient-to-br from-[#f7f7f2] to-[#eef3eb]">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-display font-semibold text-center mb-1">{t('welcomeBack')}</h1>
        <p className="text-ink-soft text-center mb-8">{t('loginSubtitle')}</p>
        <form onSubmit={handleSubmit} className="bg-white border border-line rounded-3xl p-7 flex flex-col gap-4 shadow-xl shadow-forest/5">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div>
            <label className="text-sm font-medium">{t('email')}</label>
            <input type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="field mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">{t('password')}</label>
            <input type="password" required value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="field mt-1" />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? 'Signing in…' : t('loginButton')}
          </button>
        </form>
        <p className="text-center text-sm text-ink-soft mt-4">
          {t('newHere')} <Link to="/register" className="text-forest font-medium">{t('createAccount')}</Link>
        </p>
      </div>
    </div>
  )
}

export default LoginPage
