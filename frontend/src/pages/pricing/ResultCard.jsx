import React, { Suspense } from 'react'
import { Card, CardContent } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { Skeleton } from '../../components/ui/skeleton'

const CostPieChart = React.lazy(() => import('../../components/charts/CostPieChart'))

function ResultCard({ title, item }) {
  if (!item?.is_available) {
    const emptyTitleClass = title.includes('陆')
      ? 'bg-cost-agent/30 text-cost-agent'
      : 'bg-cost-withdraw/30 text-cost-withdraw'
    return (
      <Card className="border-dashed">
        <CardContent className="py-3 px-4">
          <div className={`flex justify-between items-center p-2 rounded ${emptyTitleClass}`}>
            <span className="text-sm font-medium">{title.includes('陆') ? '陆运' : '空运'}</span>
            <span className="text-xs text-muted-foreground">无可用方案</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const savedCostPct = item.avg_cost && item.saved_cost
    ? (item.saved_cost / item.avg_cost * 100).toFixed(1)
    : null

  return (
    <Card>
      <CardContent className="py-3 px-4 space-y-3">
        {/* 标题栏 */}
        <div
          className={`flex justify-between items-center p-2 rounded ${
            title.includes('陆') ? 'bg-cost-agent/30 text-cost-agent' : 'bg-cost-withdraw/30 text-cost-withdraw'
          }`}
        >
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium">{item.logistics_name || '未知物流'}</span>
            {(item?.is_smart || (item?.logistics_name && item.logistics_name.includes('Smart'))) && (
              <Badge variant="outline" className="text-amber-500 border-amber-400 h-5 px-1 py-0 text-[10px]">Smart</Badge>
            )}
          </div>
          <span className="text-xs text-muted-foreground">{title.includes('陆') ? '陆运' : '空运'}</span>
        </div>

        {/* 售价行 */}
        <div className="flex justify-between items-center">
          <div>
            <span className="text-muted-foreground">建议售价 </span>
            <span className="text-2xl font-bold text-white">¥{item.price_cny?.toFixed(2)}</span>
          </div>
          <div className="text-sm">
            <span className="text-muted-foreground">运营利润率 </span>
            <span className="font-semibold text-cost-profit">{item.profit_margin_pct?.toFixed(1)}%</span>
          </div>
        </div>

        {/* 饼图行 */}
        {item.breakdown && item.breakdown.length > 0 && (
          <Suspense fallback={<Skeleton className="h-64 w-full" />}>
            <CostPieChart
            breakdown={item.breakdown}
            totalPrice={item.price_cny}
            netProfit={item.profit_cny}
          />
          </Suspense>
        )}

        {/* 底部3行对比数据 */}
        <div className="space-y-2">
          {/* 第1行：运费与时效 */}
          <div className="flex justify-between bg-cost-logistics/5 rounded p-1 transition-colors duration-200">
            <div className="flex justify-between flex-1 mr-2">
              <span className="text-cost-logistics">运费</span>
              <span className="text-white font-medium">¥{item.logistics_cost?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between flex-1 ml-2">
              <span className="text-cost-logistics">时效</span>
              <span className="text-white font-medium">{item.days_min}-{item.days_max}天</span>
            </div>
          </div>

          {/* 第2行：平均运费与节省运费 */}
          <div className="flex justify-between bg-cost-profit/5 rounded p-1 transition-colors duration-200">
            <div className="flex justify-between flex-1 mr-2">
              <span className="text-cost-logistics">平均运费</span>
              <span className="text-white font-medium">¥{item.avg_cost?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between flex-1 ml-2">
              <span className="text-cost-logistics">节省</span>
              <span className="text-white font-medium">{savedCostPct !== null ? `${savedCostPct > 0 ? '+' : ''}${savedCostPct}%` : '-'}</span>
            </div>
          </div>

          {/* 第3行：平均时效与节省时效 */}
          <div className="flex justify-between bg-cost-logistics/10 rounded p-1 transition-colors duration-200">
            <div className="flex justify-between flex-1 mr-2">
              <span className="text-cost-logistics">平均时效</span>
              <span className="text-white font-medium">{item.avg_days?.toFixed(1)}天</span>
            </div>
            <div className="flex justify-between flex-1 ml-2">
              <span className="text-cost-logistics">节省</span>
              <span className="text-white font-medium">{item.saved_days != null ? `${item.saved_days > 0 ? '+' : ''}${item.saved_days.toFixed(1)}天` : '-'}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default ResultCard
