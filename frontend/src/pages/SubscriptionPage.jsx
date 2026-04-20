import { useEffect, useState , useCallback } from 'react'
import { Crown, CheckCircle, Info } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog'
import PaymentQRDialog from '../components/PaymentQRDialog'
import { toast } from 'sonner'
import { useAuthStore } from '../stores/authStore'
import { subscriptionsAPI } from '../services/api'

function SubscriptionPage() {
  const { user } = useAuthStore()
  const [currentPlan, setCurrentPlan] = useState(null)
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState(null)
  const [billingCycle, setBillingCycle] = useState('month')
  const [qrDialogOpen, setQrDialogOpen] = useState(false)

  const fetchSubscription = useCallback(async () => {
    try {
      const response = await subscriptionsAPI.getCurrent()
      setCurrentPlan(response)
      return response
    } catch (error) {
      // Use mock data
      const fallback = {
        plan_code: user?.user_type || 'free',
        calc_limit: -1,
        logistics_limit: 1,
      }
      setCurrentPlan(fallback)
      return fallback
    }
  }, [user])

  const fetchPlans = useCallback(async () => {
    try {
      setLoading(true)
      const data = await subscriptionsAPI.getPlans()
      const list = Array.isArray(data) ? data : []
      setPlans(list)
    } catch (err) {
      setError('获取套餐列表失败')
      toast.error('获取套餐列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const loadInitial = async () => {
      setLoading(true)
      try {
        const [subData, plansData] = await Promise.all([
          subscriptionsAPI.getCurrent().catch(() => ({
            plan_code: user?.user_type || 'free',
            calc_limit: -1,
            logistics_limit: 1,
          })),
          subscriptionsAPI.getPlans(),
        ])
        if (!controller.signal.aborted) {
          setCurrentPlan(subData)
          setPlans(Array.isArray(plansData) ? plansData : [])
        }
      } catch {
        if (!controller.signal.aborted) {
          setError('获取套餐列表失败')
          toast.error('获取套餐列表失败')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }
    loadInitial()
    return () => controller.abort()
  }, [user])

  const handleUpgrade = useCallback((plan) => {
    setSelectedPlan(plan)
    setBillingCycle('month')
    setConfirmOpen(true)
  }, [])

  const getSelectedPrice = useCallback(() => {
    if (!selectedPlan) return 0
    if (billingCycle === 'month') {
      return Number(selectedPlan.effective_price_month ?? selectedPlan.actual_price_month ?? 0)
    }
    return Number(selectedPlan.effective_price_year ?? selectedPlan.actual_price_year ?? 0)
  }, [selectedPlan, billingCycle])

  const handleConfirmPayment = useCallback(() => {
    setConfirmOpen(false)
    setQrDialogOpen(true)
  }, [])

  const handlePaymentSuccess = useCallback(async () => {
    toast.success('支付成功，正在刷新订阅信息...')
    const sub = await fetchSubscription()
    await fetchPlans()
    // Sync auth store so sidebar/header reflect the new plan
    if (sub?.plan_code && user) {
      useAuthStore.getState().setUser({
        ...user,
        user_type: sub.plan_code,
        subscription_type: sub.plan_code,
      })
    }
  }, [fetchSubscription, fetchPlans, user])

  const getCurrentPlanName = useCallback(() => {
    const code = currentPlan?.plan_code || user?.subscription_type || user?.user_type || 'free'
    if (code === 'enterprise') return '企业版'
    if (code === 'professional') return '专业版'
    if (code === 'efficiency') return '效率版'
    return '免费版'
  }, [currentPlan, user])

  const getCalcLimitText = useCallback((limit) => {
    return limit === -1 ? '无限次' : `${limit}次/月`
  }, [])

  const getLogisticsLimitText = useCallback((limit) => {
    return limit === -1 ? '无限' : `${limit}个`
  }, [])

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-headline tracking-tight text-text-primary">
        💎 订阅管理 — 管理订阅和套餐信息
      </h1>

      <div className="bg-primary/10 border border-primary/20 rounded-lg p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-primary-dim mt-0.5" />
        <p className="text-sm text-text-secondary">
          💡 支付成功后，请点击上方&apos;刷新状态&apos;按钮查看最新账户状态
        </p>
      </div>

      {/* 当前套餐 */}
      <Card>
        <CardHeader>
          <CardTitle>📋 当前套餐</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <Crown className="w-12 h-12 text-status-warning" />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-lg font-medium text-text-primary">
                  {user?.role === 'admin' ? '管理员' : getCurrentPlanName()}
                </h2>
                {user?.role === 'admin' && (
                  <Badge variant="secondary" className="bg-status-warning/20 text-status-warning border-status-warning/30">
                    永久免费
                  </Badge>
                )}
              </div>
              <div className="flex gap-4 text-sm text-text-secondary mb-2">
                <span>计算次数: <strong className="text-text-primary">{user?.role === 'admin' ? '无限次' : getCalcLimitText(currentPlan?.calc_limit || -1)}</strong></span>
                <span>物流模板: <strong className="text-text-primary">{getLogisticsLimitText(currentPlan?.logistics_limit || 1)}</strong></span>
              </div>
              <div className="flex gap-2">
                <Badge variant="outline" className="border-status-success/30 text-status-success">永久有效</Badge>
                <Badge variant="outline" className="border-primary/30 text-primary-dim">计算次数无限</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 套餐对比 */}
      <h2 className="text-lg font-medium text-text-primary mt-8">📊 套餐对比</h2>
      
      {loading && plans.length === 0 ? (
        <div className="flex justify-center items-center py-12 text-text-secondary">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mr-3"></div>
          加载中...
        </div>
      ) : error ? (
        <div className="text-center py-12 text-status-error bg-status-error/10 rounded-lg mt-4 border border-status-error/20">
          {error}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          {plans.map((plan) => {
          const activePlanCode = currentPlan?.plan_code || user?.subscription_type || user?.user_type || 'free'
          const isCurrentPlan = activePlanCode === plan.code || (user?.role === 'admin' && plan.code === 'free')
          return (
            <Card 
              key={plan.code} 
              className={`relative flex flex-col transition-all duration-200 hover:-translate-y-1 hover:shadow-lg ${isCurrentPlan ? 'ring-2 ring-primary' : ''}`}
            >
              {isCurrentPlan && (
                <Badge className="absolute top-3 right-3 bg-primary">当前</Badge>
              )}
              {plan.developing && (
                <Badge className="absolute top-3 right-3 bg-status-warning">开发中</Badge>
              )}
              
              <CardContent className="flex-1 flex flex-col pt-10">
                <div className="text-center mb-4">
                  <Crown className={`w-9 h-9 mx-auto ${plan.code === 'professional' ? 'text-status-warning' : 'text-text-muted'}`} />
                  <h3 className="text-lg font-medium text-text-primary mt-2">{plan.name}</h3>
                </div>

                <div className="text-center mb-4">
                  {plan.display_price_month === 0 ? (
                    <span className="text-lg font-semibold text-text-primary">免费</span>
                  ) : (
                    <div>
                      <div className="text-2xl font-bold text-text-primary">¥{Number(plan.display_price_month).toFixed(2)}<span className="text-sm font-normal text-text-secondary">/月</span></div>
                      <div className="text-sm text-text-secondary">¥{Number(plan.display_price_year).toFixed(2)}/年</div>
                    </div>
                  )}
                </div>

                <div className="text-sm text-text-secondary mb-4 space-y-1">
                  <div>计算次数: <strong className="text-text-primary">{getCalcLimitText(plan.calc_limit)}</strong></div>
                  <div>物流模板: <strong className="text-text-primary">{getLogisticsLimitText(plan.logistics_limit)}</strong></div>
                </div>

                <div className="mb-4 flex-1">
                  {plan.features.map((f) => (
                    <div key={f} className="flex items-start text-sm text-text-secondary mb-2">
                      <CheckCircle className="w-4 h-4 text-status-success mr-2 mt-0.5 shrink-0" />
                      <span>{f}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
              
              <div className="p-6 pt-0 mt-auto">
                {plan.code === 'enterprise' ? (
                  <Button 
                    className="w-full" 
                    disabled={plan.developing}
                    variant={plan.developing ? "secondary" : "default"}
                  >
                    联系客服升级
                  </Button>
                ) : isCurrentPlan ? (
                  <Button variant="outline" className="w-full" disabled>
                    当前套餐
                  </Button>
                ) : plan.display_price_month === 0 ? null : (
                  <Button 
                    className="w-full"
                    onClick={() => handleUpgrade(plan)}
                  >
                    升级到{plan.name}
                  </Button>
                )}
              </div>
            </Card>
          )
        })}
        </div>
      )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-w-md bg-surface-container border-surface-high">
          <DialogHeader>
            <DialogTitle className="font-headline">确认升级</DialogTitle>
            <DialogDescription>选择计费周期并确认支付</DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="text-center">
              <p className="text-lg font-semibold text-text-primary">升级到 {selectedPlan?.name}</p>
            </div>

            <div className="flex gap-2 justify-center">
              <Button
                variant={billingCycle === 'month' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setBillingCycle('month')}
              >
                按月
              </Button>
              <Button
                variant={billingCycle === 'year' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setBillingCycle('year')}
              >
                按年
              </Button>
            </div>

            <div className="text-center space-y-1">
              <p className="text-3xl font-bold text-primary">
                ¥{getSelectedPrice().toFixed(2)}
              </p>
              <p className="text-sm text-text-muted">
                {billingCycle === 'month' ? '每月' : '每年'}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>取消</Button>
            <Button onClick={handleConfirmPayment}>确认支付</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PaymentQRDialog
        open={qrDialogOpen}
        onOpenChange={setQrDialogOpen}
        planCode={selectedPlan?.code || ''}
        planName={selectedPlan?.name || ''}
        billingCycle={billingCycle}
        amount={getSelectedPrice()}
        onSuccess={handlePaymentSuccess}
      />
    </div>
  )
}

export default SubscriptionPage
