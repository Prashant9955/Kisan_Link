import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Sidebar(){
  const {user}=useAuth()
  if(!user) return null
  const links=[
    ...(user.role==='farmer'?[['/farmer','🌾 My Crops']]:[]),
    ...(user.role==='buyer'?[['/buyer','🛒 Browse Crops'],['/fpo-lots','📦 FPO Lots'],['/demands','📋 Demands']]:[]),
    ...(user.role==='warehouse_owner'||user.role==='transporter'?[['/partner','🤝 Partner onboarding']]:[]),
    ['/orders','🧾 Orders'],['/payments','💳 Payments'],['/logistics','🚚 Logistics'],['/storage','🏬 Storage'],['/trust','🛡️ Trust & Disputes'],['/profit-dashboard','📊 Profit Dashboard'],['/profile','👤 Profile'],['/market-prices','📈 Market Prices'],['/mandis','🗺️ Mandi Map']
  ]
  return <aside className="hidden lg:block w-64 shrink-0"><div className="sticky top-24 soft-card p-3"><p className="px-3 py-2 text-xs font-bold uppercase tracking-widest text-ink-soft">Workspace</p>{links.map(([to,label])=><NavLink key={to} to={to} className={({isActive})=>`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${isActive?'bg-forest text-white':'text-ink hover:bg-forest/5'}`}>{label}</NavLink>)}</div></aside>
}
