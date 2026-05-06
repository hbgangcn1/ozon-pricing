import { useEffect, Suspense, lazy } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useAuthStore } from './stores/authStore'
import { useTokenRefresh } from './hooks/useTokenRefresh'
import { Skeleton } from './components/ui/skeleton'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/AppLayout'
import SessionKickedDialog from './components/SessionKickedDialog'

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

function buildLoginRedirect(location) {
  // 根路径不带 returnTo,避免登录后跳 / 又被弹回 /login 死循环
  if (!location || location.pathname === '/' || location.pathname === '') {
    return '/login'
  }
  const target = `${location.pathname}${location.search || ''}`
  return `/login?returnTo=${encodeURIComponent(target)}`
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuthStore()
  const location = useLocation()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="w-48 h-8" />
      </div>
    )
  }
  return isAuthenticated ? children : <Navigate to={buildLoginRedirect(location)} replace />
}

function AdminRoute({ children }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuthStore()
  const location = useLocation()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="w-48 h-8" />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to={buildLoginRedirect(location)} replace />
  if (!isAdmin()) return <Navigate to="/pricing" replace />
  return children
}

function App() {
  const navigate = useNavigate()
  const initAuth = useAuthStore((state) => state.initAuth)
  const sessionKicked = useAuthStore((state) => state.sessionKicked)
  const clearSessionKicked = useAuthStore((state) => state.clearSessionKicked)

  useTokenRefresh()

  useEffect(() => {
    initAuth()
  }, [initAuth])

  const handleSessionKickedConfirm = () => {
    clearSessionKicked()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <Toaster position="top-center" richColors />
      <SessionKickedDialog
        open={sessionKicked.open}
        reason={sessionKicked.reason}
        onConfirm={handleSessionKickedConfirm}
      />
      <ErrorBoundary>
        <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Skeleton className="w-48 h-8" /></div>}>
          <Routes>
            {/* 根路径永远跳登录页,无论登录态 */}
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            {/* 业务页:无 path 父路由 + 绝对路径子路由,保持扁平 URL */}
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/logistics" element={<LogisticsPage />} />
              <Route path="/account" element={<AccountPage />} />
              <Route path="/subscription" element={<SubscriptionPage />} />
              <Route path="/payment" element={<PaymentPage />} />
              <Route path="/commission-categories" element={<CommissionCategoriesPage />} />
              <Route path="/logistics-pool" element={<LogisticsPoolPage />} />
              <Route path="/product-import" element={<ProductImportPage />} />
              <Route
                path="/settings"
                element={
                  <AdminRoute>
                    <SettingsPage />
                  </AdminRoute>
                }
              />
              <Route
                path="/users"
                element={
                  <AdminRoute>
                    <UserManagementPage />
                  </AdminRoute>
                }
              />
              <Route
                path="/plans"
                element={
                  <AdminRoute>
                    <PlanManagementPage />
                  </AdminRoute>
                }
              />
              <Route
                path="/statistics"
                element={
                  <AdminRoute>
                    <StatisticsPage />
                  </AdminRoute>
                }
              />
              <Route path="/about" element={<AboutPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </>
  )
}

export default App
