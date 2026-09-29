import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { getApiError } from '../api/api'
import { useAuth } from '../context/AuthContext'

const VerificationPage = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [documentType, setDocumentType] = useState('aadhaar')
  const [document, setDocument] = useState(null)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const loadStatus = async () => {
    try {
      const { data } = await api.get('/auth/verification-status')
      setStatus(data)
    } catch (err) { setError(getApiError(err, 'Verification status could not be loaded.')) }
  }

  useEffect(() => { loadStatus() }, [])

  const upload = async (e) => {
    e.preventDefault()
    if (!document) return setError('Please choose a document first.')
    setError(''); setMessage(''); setLoading(true)
    try {
      const body = new FormData()
      body.append('documentType', documentType)
      body.append('document', document)
      await api.post('/auth/verification-document', body, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMessage('Document submitted successfully for review.')
      setDocument(null)
      e.target.reset()
      await loadStatus()
    } catch (err) { setError(getApiError(err, 'Document upload failed.')) }
    finally { setLoading(false) }
  }

  const goDashboard = () => navigate(user?.role === 'buyer' ? '/buyer' : '/farmer')

  return (
    <div className="page-shell max-w-2xl">
      <div className="soft-card p-6 md:p-8">
        <p className="eyebrow">TRUST & SAFETY</p>
        <h1 className="text-3xl font-display font-semibold mt-2">Identity verification</h1>
        <p className="text-ink-soft mt-2">Submit one document so our admin team can review your account.</p>
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        {message && <p className="mt-4 text-sm text-forest">{message}</p>}
        {status && <div className="mt-5 rounded-2xl border border-line p-4 text-sm space-y-1"><p>Phone: <b>{status.phoneVerified ? 'Verified' : 'Not verified'}</b></p><p>Documents: <b className="capitalize">{status.documentVerificationStatus?.replace('_', ' ')}</b></p></div>}
        <form onSubmit={upload} className="mt-6 space-y-4">
          <select className="field" value={documentType} onChange={(e) => setDocumentType(e.target.value)}><option value="aadhaar">Aadhaar</option><option value="pan">PAN</option><option value="gst">GST</option><option value="other">Other</option></select>
          <input required type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setDocument(e.target.files?.[0] || null)} className="field" />
          <p className="text-xs text-ink-soft">Accepted: PDF, JPG, JPEG, PNG. Maximum 5 MB. Use a test document during development.</p>
          <button disabled={loading} className="btn-primary w-full">{loading ? 'Uploading…' : 'Submit document'}</button>
        </form>
        <button onClick={goDashboard} className="btn-secondary w-full mt-3">Continue to dashboard</button>
      </div>
    </div>
  )
}

export default VerificationPage
