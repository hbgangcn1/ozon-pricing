import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useAuthStore } from './stores/authStore'
import { Skeleton } from './components/ui/skeleton'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import PricingPage from './pages/PricingPage'
import LogisticsPage from './pages/LogisticsPage'
import Layout from './components/AppLayout'
import AccountPage from './pages/AccountPage'
import SubscriptionPage from './pages/SubscriptionPage'
import PaymentPage from './pages/PaymentPage'
import SettingsPage from './pages/SettingsPage'
import UserManagementPage from './pages/UserManagementPage'
import PlanManagementPage from './pages/PlanManagementPage'
import StatisticsPage from './pages/StatisticsPage'
import AboutPage from './pages/AboutPage'

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuthStore()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="w-48 h-8" />
      </div>
    )
  }
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuthStore()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="w-48 h-8" />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isAdmin()) return <Navigate to="/pricing" replace />
  return children
}

function App() {
  const { initAuth } = useAuthStore()

  useEffect(() => {
    initAuth()
  }, [initAuth])

  return (
    <>
      <Toaster position="top-center" richColors />
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
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
    </>
  )
}

export default App
