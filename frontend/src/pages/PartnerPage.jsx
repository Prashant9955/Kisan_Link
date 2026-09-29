import { useState } from 'react'
import api from '../api/api'
import { useAuth } from '../context/AuthContext'

export default function PartnerPage(){
 const {user}=useAuth(); const [msg,setMsg]=useState(''); const [error,setError]=useState('');
 const [form,setForm]=useState(user?.role==='transporter'?{name:'',phone:'',vehicleType:'',baseRatePerKm:18,minFare:250,serviceArea:''}:{name:'',location:'',capacity:100,availableCapacity:100,unit:'quintal',costPerUnit:0,contact:''})
 const update=k=>e=>setForm({...form,[k]:e.target.value})
 const submit=async e=>{e.preventDefault();setMsg('');setError('');try{await api.post(user.role==='transporter'?'/partner/transporters':'/partner/warehouses',form);setMsg('Submitted. Admin approval is required before listing.')}catch(e){setError(e.response?.data?.detail||'Submission failed')}}
 return <div className="page-shell"><h1 className="text-4xl font-display font-semibold">Partner onboarding</h1><p className="text-ink-soft mt-2">{user?.role==='transporter'?'Register your transport service':'Register your warehouse'}. Admin approval is required.</p><form onSubmit={submit} className="soft-card p-6 mt-6 grid md:grid-cols-2 gap-4">{Object.keys(form).map(k=><input key={k} className="field" placeholder={k} type={['capacity','availableCapacity','costPerUnit','baseRatePerKm','minFare'].includes(k)?'number':'text'} value={form[k]} onChange={update(k)} required={['name','location','phone','vehicleType'].includes(k)}/>)}<button className="btn-primary md:col-span-2">Submit for approval</button>{msg&&<p className="text-green-700">{msg}</p>}{error&&<p className="text-red-600">{error}</p>}</form></div>
}
