import { useEffect, useState } from 'react'
import api, { getApiError } from '../api/api'

export default function FpoLotsPage() {
  const [search, setSearch] = useState('')
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [lots, setLots] = useState([])
  const [selected, setSelected] = useState(null)
  const [amount, setAmount] = useState('')
  const [quantity, setQuantity] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [saving, setSaving] = useState(false)
  const load = async () => { try { const { data } = await api.get('/lots/search', { params: { search: search || undefined, verifiedOnly } }); setLots(data); setError('') } catch (e) { setError(getApiError(e, 'Lots could not be loaded.')) } }
  useEffect(() => { load() }, [verifiedOnly])
  const placeBid = async (e) => {
    e.preventDefault(); if (!selected) return
    setSaving(true); setError(''); setSuccess('')
    try { await api.post('/bids', { cropId: selected._id, amountPerUnit: Number(amount), quantity: Number(quantity) }); setSuccess('Offer placed successfully. The farmer will review it.'); setSelected(null); setAmount(''); setQuantity('') }
    catch (e) { setError(getApiError(e, 'Offer could not be placed.')) } finally { setSaving(false) }
  }
  return <div className="page-shell"><div className="mb-6"><p className="eyebrow">STEP 2 · LOT DISCOVERY · STEP 4 · QUALITY · STEP 5 · OFFERS</p><h1 className="text-4xl font-display font-semibold mt-2">FPO & Farmer Lots</h1><p className="text-ink-soft mt-2">Search available lots, inspect quality information and place a direct offer.</p></div><div className="soft-card p-4 flex flex-col md:flex-row gap-3 mb-6"><input className="field flex-1" placeholder="Search crop name" value={search} onChange={e=>setSearch(e.target.value)}/><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={verifiedOnly} onChange={e=>setVerifiedOnly(e.target.checked)}/> Verified only</label><button className="btn-primary" onClick={load}>Search</button></div>{error&&<p className="text-red-600 mb-4">{error}</p>}{success&&<p className="text-forest mb-4">{success}</p>}<div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">{lots.map(l=><div className="soft-card p-5" key={l._id}><div className="flex justify-between gap-2"><h3 className="font-display text-xl font-semibold">{l.name}</h3><span className="text-xs rounded-full bg-forest/10 px-2 py-1">{l.lotType}</span></div><p className="text-sm text-ink-soft mt-2">{l.quantity} {l.unit} · ₹{l.pricePerUnit}/{l.unit}</p><p className="text-sm mt-3">Farmer: <b>{l.farmer?.name || 'Unknown'}</b></p><p className="text-sm">Organization: {l.farmer?.organization || 'Individual farmer'}</p><p className="text-sm mt-2">Verification: <b className={l.farmerVerification?.verified?'text-forest':'text-amber-700'}>{l.farmerVerification?.verified?'Verified':'Pending / incomplete'}</b></p><div className="mt-3 text-xs text-ink-soft space-y-1"><p>Variety: {l.variety || 'Not specified'}</p><p>Grade: {l.grade || 'Not specified'}</p><p>Moisture: {l.moisture ?? '—'}{l.moisture != null ? '%' : ''}</p><p>Packaging: {l.packaging || 'Not specified'}</p></div><p className="text-xs text-ink-soft mt-3">{l.description || 'No additional quality details provided.'}</p><button className="btn-primary w-full mt-4" onClick={()=>setSelected(l)}>Place offer</button></div>)}</div>{!lots.length&&<div className="soft-card p-10 text-center text-ink-soft">No matching lots found.</div>}{selected&&<div className="fixed inset-0 bg-black/40 grid place-items-center p-4 z-50"><form onSubmit={placeBid} className="bg-white rounded-3xl p-6 w-full max-w-md space-y-4"><div><h2 className="text-2xl font-display font-semibold">Offer for {selected.name}</h2><p className="text-sm text-ink-soft mt-1">Available: {selected.quantity} {selected.unit}</p></div><input required type="number" min="0.01" step="any" className="field" placeholder={`Your price per ${selected.unit}`} value={amount} onChange={e=>setAmount(e.target.value)}/><input required type="number" min="0.01" max={selected.quantity} step="any" className="field" placeholder={`Quantity in ${selected.unit}`} value={quantity} onChange={e=>setQuantity(e.target.value)}/><div className="flex gap-2"><button disabled={saving} className="btn-primary flex-1">{saving?'Submitting…':'Submit offer'}</button><button type="button" className="btn-secondary" onClick={()=>setSelected(null)}>Cancel</button></div></form></div>}</div>
}
