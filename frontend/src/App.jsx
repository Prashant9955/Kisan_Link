import { Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import VerifyPhonePage from './pages/VerifyPhonePage'
import VerificationPage from './pages/VerificationPage'
import FarmerDashboard from './pages/FarmerDashboard'
import BuyerDashboard from './pages/BuyerDashboard'
import OrdersPage from './pages/OrdersPage'
import MandiMapPage from './pages/MandiMapPage'
import ProtectedRoute from './components/ProtectedRoute'
import HomePage from './pages/HomePage'
import MarketPricesPage from './pages/MarketPricesPage'
import PriceInsightsPage from './pages/PriceInsightsPage'
import AdminDashboard from './pages/AdminDashboard'
import ProfilePage from './pages/ProfilePage'
import ProfitDashboard from './pages/ProfitDashboard'
import FpoLotsPage from './pages/FpoLotsPage'
import DemandPage from './pages/DemandPage'
import PaymentTrackingPage from './pages/PaymentTrackingPage'
import LogisticsPage from './pages/LogisticsPage'
import Sidebar from './components/Sidebar'
import StoragePage from './pages/StoragePage'
import TrustPage from './pages/TrustPage'
import PartnerPage from './pages/PartnerPage'
import { useAuth } from './context/AuthContext'

function App() {
  const { user } = useAuth()

  return (
    <>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex gap-6 items-start">
        <Sidebar />
        <main className="min-w-0 flex-1">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-phone" element={<VerifyPhonePage />} />
        <Route path="/verification" element={<ProtectedRoute><VerificationPage /></ProtectedRoute>} />
        <Route path="/mandis" element={<MandiMapPage />} />
        <Route path="/market-prices" element={<MarketPricesPage />} />
        <Route path="/price-insights" element={<PriceInsightsPage />} />
        <Route path="/farmer" element={<ProtectedRoute role="farmer"><FarmerDashboard /></ProtectedRoute>} />
        <Route path="/buyer" element={<ProtectedRoute role="buyer"><BuyerDashboard /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
        <Route path="/orders" element={<ProtectedRoute><OrdersPage /></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/profit-dashboard" element={<ProtectedRoute><ProfitDashboard /></ProtectedRoute>} />
        <Route path="/fpo-lots" element={<ProtectedRoute role="buyer"><FpoLotsPage /></ProtectedRoute>} />
        <Route path="/demands" element={<ProtectedRoute role="buyer"><DemandPage /></ProtectedRoute>} />
        <Route path="/payments" element={<ProtectedRoute><PaymentTrackingPage /></ProtectedRoute>} />
        <Route path="/logistics" element={<ProtectedRoute><LogisticsPage /></ProtectedRoute>} />
        <Route path="/storage" element={<ProtectedRoute><StoragePage /></ProtectedRoute>} />
        <Route path="/trust" element={<ProtectedRoute><TrustPage /></ProtectedRoute>} />
        <Route path="/partner" element={<ProtectedRoute><PartnerPage /></ProtectedRoute>} />
      </Routes>
        </main>
      </div>
    </>
  )
}

export default App
