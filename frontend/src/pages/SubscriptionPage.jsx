import { useEffect, useState } from 'react'
import { Crown, CheckCircle, ArrowUp, Info } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { toast } from 'sonner'
import { useAuthStore } from '../stores/authStore'

const mockPlans = [
  {
    code: 'free',
    name: '免费版',
    display_price_month: 0,
    display_price_year: 0,
    calc_limit: 10,
    logistics_limit: 1,
    features: ['极速模式', '基础物流模板'],
    is_current: true,
  },
  {
    code: 'efficiency',
    name: '效率版',
    display_price_month: 9.9,
    display_price_year: 99,
    calc_limit: -1,
    logistics_limit: 3,
    features: ['无限极速模式', '3个物流模板'],
    is_current: false,
  },
  {
    code: 'professional',
    name: '专业版',
    display_price_month: 149,
    display_price_year: 1499,
    calc_limit: -1,
    logistics_limit: -1,
    features: ['极速+精准模式', '无限物流模板', '多物流比价'],
    is_current: false,
  },
  {
    code: 'enterprise',
    name: '企业版',
    display_price_month: 999,
    display_price_year: 9999,
    calc_limit: -1,
    logistics_limit: -1,
    features: ['专业版所有功能', 'API级活动监控', '专属客服'],
    is_current: false,
    developing: true,
  },
]

function SubscriptionPage() {
  const { user } = useAuthStore()
  const [currentPlan, setCurrentPlan] = useState(null)
  const [plans, setPlans] = useState(mockPlans)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchSubscription()
  }, [])

  const fetchSubscription = async () => {
    try {
      const response = await subscriptionAPI.getCurrent()
      setCurrentPlan(response)
    } catch (error) {
      // Use mock data
      setCurrentPlan({
        plan_code: user?.user_type || 'free',
        calc_limit: -1,
        logistics_limit: 1,
      })
    }
  }

  const handleUpgrade = (planCode) => {
    toast.info(`升级到${planCode}功能开发中，请联系客服`)
  }

  const getCurrentPlanName = () => {
    if (user?.user_type === 'enterprise') return '企业版'
    if (user?.user_type === 'professional') return '专业版'
    if (user?.user_type === 'efficiency') return '效率版'
    return '免费版'
  }

  const getCalcLimitText = (limit) => {
    return limit === -1 ? '无限次' : `${limit}次/月`
  }

  const getLogisticsLimitText = (limit) => {
    return limit === -1 ? '无限' : `${limit}个`
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-headline tracking-tight text-text-primary">
        💎 订阅管理 — 管理订阅和套餐信息
      </h1>

      <div className="bg-primary/10 border border-primary/20 rounded-lg p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-primary-dim mt-0.5" />
        <p className="text-sm text-text-secondary">
          💡 支付成功后，请点击上方'刷新状态'按钮查看最新账户状态
        </p>
      </div>

      {/* 当前套餐 */}
      <Card>
        <CardHeader>
          <CardTitle>📋 当前套餐</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <Crown className="w-12 h-12 text-yellow-500" />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-lg font-medium text-text-primary">
                  {user?.role === 'admin' ? '管理员' : getCurrentPlanName()}
                </h2>
                {user?.role === 'admin' && (
                  <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                    永久免费
                  </Badge>
                )}
              </div>
              <div className="flex gap-4 text-sm text-text-secondary mb-2">
                <span>计算次数: <strong className="text-text-primary">{user?.role === 'admin' ? '无限次' : getCalcLimitText(currentPlan?.calc_limit || -1)}</strong></span>
                <span>物流模板: <strong className="text-text-primary">{getLogisticsLimitText(currentPlan?.logistics_limit || 1)}</strong></span>
              </div>
              <div className="flex gap-2">
                <Badge variant="outline" className="border-green-500/30 text-green-400">永久有效</Badge>
                <Badge variant="outline" className="border-primary/30 text-primary-dim">计算次数无限</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 套餐对比 */}
      <h2 className="text-lg font-medium text-text-primary mt-8">📊 套餐对比</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        {plans.map((plan) => {
          const isCurrentPlan = user?.user_type === plan.code || (user?.role === 'admin' && plan.code === 'free')
          return (
            <Card 
              key={plan.code} 
              className={`relative flex flex-col transition-all duration-200 hover:-translate-y-1 hover:shadow-lg ${isCurrentPlan ? 'ring-2 ring-primary' : ''}`}
            >
              {isCurrentPlan && (
                <Badge className="absolute top-3 right-3 bg-primary">当前</Badge>
              )}
              {plan.developing && (
                <Badge className="absolute top-3 right-3 bg-orange-500">开发中</Badge>
              )}
              
              <CardContent className="flex-1 flex flex-col pt-10">
                <div className="text-center mb-4">
                  <Crown className={`w-9 h-9 mx-auto ${plan.code === 'professional' ? 'text-yellow-500' : 'text-text-muted'}`} />
                  <h3 className="text-lg font-medium text-text-primary mt-2">{plan.name}</h3>
                </div>

                <div className="text-center mb-4">
                  {plan.display_price_month === 0 ? (
                    <span className="text-lg font-semibold text-text-primary">免费</span>
                  ) : (
                    <div>
                      <div className="text-2xl font-bold text-text-primary">¥{plan.display_price_month}<span className="text-sm font-normal text-text-secondary">/月</span></div>
                      <div className="text-sm text-text-secondary">¥{plan.display_price_year}/年</div>
                    </div>
                  )}
                </div>

                <div className="text-sm text-text-secondary mb-4 space-y-1">
                  <div>计算次数: <strong className="text-text-primary">{getCalcLimitText(plan.calc_limit)}</strong></div>
                  <div>物流模板: <strong className="text-text-primary">{getLogisticsLimitText(plan.logistics_limit)}</strong></div>
                </div>

                <div className="mb-4 flex-1">
                  {plan.features.map((f, i) => (
                    <div key={i} className="flex items-start text-sm text-text-secondary mb-2">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2 mt-0.5 shrink-0" />
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
                ) : (
                  <Button 
                    className="w-full"
                    onClick={() => handleUpgrade(plan.code)}
                  >
                    升级到{plan.name}
                  </Button>
                )}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

export default SubscriptionPage

