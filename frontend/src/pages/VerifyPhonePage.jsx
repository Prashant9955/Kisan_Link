import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api, { getApiError } from '../api/api'
import { useAuth } from '../context/AuthContext'

const VerifyPhonePage = () => {
  const params = new URLSearchParams(useLocation().search)
  const userId = params.get('userId') || ''
  const email = params.get('email') || ''
  const [otp, setOtp] = useState('')
  const [devOtp, setDevOtp] = useState(params.get('devOtp') || '')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { verifyPhone } = useAuth()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      await verifyPhone(userId, otp)
      navigate('/verification')
    } catch (err) {
      setError(getApiError(err, 'OTP verification failed.'))
    } finally {
      setLoading(false)
    }
  }

  const resend = async () => {
    setError('')
    setMessage('')
    try {
      const { data } = await api.post('/auth/resend-otp', { userId })
      setDevOtp(data.devOtp || '')
      setMessage('A new OTP has been generated.')
    } catch (err) {
      setError(getApiError(err, 'Could not resend OTP.'))
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-gradient-to-br from-[#f7f7f2] to-[#eef3eb]">
      <form onSubmit={submit} className="w-full max-w-sm bg-white border border-line rounded-3xl p-7 shadow-xl shadow-forest/5 space-y-4">
        <div>
          <p className="eyebrow">ACCOUNT SECURITY</p>
          <h1 className="text-3xl font-display font-semibold mt-2">Verify your phone</h1>
          <p className="text-sm text-ink-soft mt-2">Enter the 6-digit OTP sent for {email}.</p>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {message && <p className="text-sm text-forest">{message}</p>}
        {devOtp && <div className="rounded-xl bg-gold-soft px-3 py-2 text-sm">Development OTP: <b>{devOtp}</b></div>}
        <input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} placeholder="Enter 6-digit OTP" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} className="field" />
        <button disabled={loading} className="btn-primary w-full">{loading ? 'Verifying…' : 'Verify phone'}</button>
        <button type="button" onClick={resend} className="btn-secondary w-full">Resend OTP</button>
      </form>
    </div>
  )
}

export default VerifyPhonePage
