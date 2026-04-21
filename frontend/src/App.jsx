import { useEffect, Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useAuthStore } from './stores/authStore'
import { Skeleton } from './components/ui/skeleton'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/AppLayout'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'))
const PricingPage = lazy(() => import('./pages/PricingPage'))
const LogisticsPage = lazy(() => import('./pages/LogisticsPage'))
const AccountPage = lazy(() => import('./pages/AccountPage'))
const SubscriptionPage = lazy(() => import('./pages/SubscriptionPage'))
const PaymentPage = lazy(() => import('./pages/PaymentPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'))
const PlanManagementPage = lazy(() => import('./pages/PlanManagementPage'))
const StatisticsPage = lazy(() => import('./pages/StatisticsPage'))
const AboutPage = lazy(() => import('./pages/AboutPage'))
const CommissionCategoriesPage = lazy(() => import('./pages/CommissionCategoriesPage'))
const LogisticsPoolPage = lazy(() => import('./pages/LogisticsPoolPage'))
const ProductImportPage = lazy(() => import('./pages/ProductImportPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

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
      <ErrorBoundary>
        <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Skeleton className="w-48 h-8" /></div>}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
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
              <Route path="commission-categories" element={<CommissionCategoriesPage />} />
              <Route path="logistics-pool" element={<LogisticsPoolPage />} />
              <Route path="product-import" element={<ProductImportPage />} />
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
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </>
  )
}

export default App
