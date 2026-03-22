import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import LoginPage from './pages/LoginPage'
import PricingPage from './pages/PricingPage'
import LogisticsPage from './pages/LogisticsPage'
import Layout from './components/Layout'
import AccountPage from './pages/AccountPage'
import SubscriptionPage from './pages/SubscriptionPage'
import PaymentPage from './pages/PaymentPage'
import SettingsPage from './pages/SettingsPage'
import UserManagementPage from './pages/UserManagementPage'
import PlanManagementPage from './pages/PlanManagementPage'
import StatisticsPage from './pages/StatisticsPage'
import AboutPage from './pages/AboutPage'

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const { isAuthenticated, isAdmin } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isAdmin()) return <Navigate to="/pricing" replace />
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<PricingPage />} />
        <Route path="pricing" element={<PricingPage />} />
        <Route path="logistics" element={<LogisticsPage />} />
        <Route path="account" element={<AccountPage />} />
        <Route path="subscription" element={<SubscriptionPage />} />
        <Route path="payment" element={<PaymentPage />} />
        <Route
          path="settings"
          element={
            <AdminRoute>
              <SettingsPage />
            </AdminRoute>
          }
        />
        <Route
          path="users"
          element={
            <AdminRoute>
              <UserManagementPage />
            </AdminRoute>
          }
        />
        <Route
          path="plans"
          element={
            <AdminRoute>
              <PlanManagementPage />
            </AdminRoute>
          }
        />
        <Route
          path="statistics"
          element={
            <AdminRoute>
              <StatisticsPage />
            </AdminRoute>
          }
        />
        <Route path="about" element={<AboutPage />} />
      </Route>
    </Routes>
  )
}

export default App
