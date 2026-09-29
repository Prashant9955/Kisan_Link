import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'

const RegisterPage = () => {
  const [form, setForm] = useState({ name: '', email: '', password: '', phone: '', role: 'farmer', location: '', organization: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await register(form)
      navigate(`/verify-phone?userId=${data.userId}&email=${encodeURIComponent(data.email)}${data.devOtp ? `&devOtp=${data.devOtp}` : ''}`)
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Registration failed')
    } finally { setLoading(false) }
  }

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-gradient-to-br from-[#f7f7f2] to-[#eef3eb]">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-display font-semibold text-center mb-1">{t('createAccountTitle')}</h1>
        <p className="text-ink-soft text-center mb-8">{t('registerSubtitle')}</p>
        <form onSubmit={handleSubmit} className="bg-white border border-line rounded-3xl p-7 flex flex-col gap-4 shadow-xl shadow-forest/5">
          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="grid grid-cols-2 gap-3">
            <button type="button" onClick={() => setForm({ ...form, role: 'farmer' })}
              className={`rounded-md py-2 text-sm font-medium border ${form.role === 'farmer' ? 'bg-forest text-white border-forest' : 'border-line text-ink-soft'}`}>
              {t('imFarmer')}
            </button>
            <button type="button" onClick={() => setForm({ ...form, role: 'buyer' })}
              className={`rounded-md py-2 text-sm font-medium border ${form.role === 'buyer' ? 'bg-forest text-white border-forest' : 'border-line text-ink-soft'}`}>
              {t('imBuyer')}
            </button>
          </div>
          <select className="field" value={form.role} onChange={update('role')}><option value="farmer">Farmer</option><option value="buyer">Buyer</option><option value="warehouse_owner">Warehouse Owner</option><option value="transporter">Transporter</option></select>

          <div>
            <label className="text-sm font-medium">{t('fullName')}</label>
            <input required value={form.name} onChange={update('name')}
              className="field mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">{t('email')}</label>
            <input type="email" required value={form.email} onChange={update('email')}
              className="field mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">{t('phone')}</label>
            <input required value={form.phone} onChange={update('phone')}
              className="field mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">{t('villageDistrict')}</label>
            <input value={form.location} onChange={update('location')}
              className="field mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">{t('password')}</label>
            <input type="password" required minLength={6} value={form.password} onChange={update('password')}
              className="field mt-1" />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? 'Creating account…' : t('createAccountButton')}
          </button>
        </form>
        <p className="text-center text-sm text-ink-soft mt-4">
          {t('alreadyRegistered')} <Link to="/login" className="text-forest font-medium">{t('loginButton')}</Link>
        </p>
      </div>
    </div>
  )
}

export default RegisterPage
