import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { useRealtime } from '../context/RealtimeContext'

const Navbar = () => {
  const { user, logout } = useAuth(); const { lang, setLang, t } = useLanguage(); const { notifications } = useRealtime(); const navigate = useNavigate()
  const links = user?.role === 'farmer' ? [['/farmer',t('myCrops')]] : user?.role === 'buyer' ? [['/buyer',t('browseCrops')]] : user?.role === 'admin' ? [['/admin','Admin']] : []
  return <header className="sticky top-0 z-50 border-b border-white/10 bg-forest/95 backdrop-blur text-cream shadow-lg shadow-forest/10">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
      <Link to="/" className="flex items-center gap-2.5 shrink-0"><span className="grid place-items-center w-9 h-9 rounded-xl bg-gold text-ink font-black">K</span><span className="font-display text-xl font-semibold tracking-tight">Kisan Bazaar</span></Link>
      <nav className="hidden md:flex items-center gap-5 text-sm text-cream/85">{links.map(([href,label])=><Link key={href} to={href} className="hover:text-gold transition">{label}</Link>)}{user&&<Link to="/orders" className="hover:text-gold transition">{t('orders')}</Link>} {user?.role==='buyer'&&<><Link to="/fpo-lots" className="hover:text-gold transition">FPO Lots</Link><Link to="/demands" className="hover:text-gold transition">Post Demand</Link></>} {user&&<Link to="/profit-dashboard" className="hover:text-gold transition">Profit Dashboard</Link>}<Link to="/mandis" className="hover:text-gold transition">{t('mandiMap')}</Link><Link to="/market-prices" className="hover:text-gold transition">Market Prices</Link></nav>
      <div className="flex items-center gap-2"><button title="Language" onClick={()=>setLang(lang==='en'?'hi':'en')} className="rounded-lg border border-white/20 px-2.5 py-1.5 text-xs hover:border-gold hover:text-gold">{lang==='en'?'हिंदी':'English'}</button>{user&&<span className="hidden lg:inline-flex text-xs bg-white/10 rounded-full px-3 py-1.5">{notifications.length ? `🔔 ${notifications.length}` : '🔔'}</span>}{user?<><button title="Profile" onClick={()=>navigate('/profile')} className="w-9 h-9 rounded-full bg-gold text-ink font-bold text-xs hover:scale-105 transition">{(user.name||'U').slice(0,2).toUpperCase()}</button><button onClick={()=>{logout();navigate('/login')}} className="text-sm hover:text-gold">{t('logout')}</button></>:<><Link to="/login" className="hidden sm:block text-sm hover:text-gold">{t('login')}</Link><Link to="/register" className="bg-gold text-ink px-3.5 py-2 rounded-xl text-sm font-bold hover:brightness-95">{t('signUp')}</Link></>}</div>
    </div>
  </header>
}
export default Navbar
