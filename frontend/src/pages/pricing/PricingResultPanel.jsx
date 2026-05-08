import React, { Suspense } from 'react'
import { ChevronDown } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs'
import { Badge } from '../../components/ui/badge'
import { Skeleton } from '../../components/ui/skeleton'
import { Label } from '../../components/ui/label'
import { Switch } from '../../components/ui/switch'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../../components/ui/collapsible'
import { CIS_COUNTRIES } from './pricingConstants'
import { getActiveFilteredLogistics, getGroupedData } from './pricingUtils'

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
        <div className={`flex justify-between items-center p-2 rounded ${title.includes('陆') ? 'bg-cost-agent/30 text-cost-agent' : 'bg-cost-withdraw/30 text-cost-withdraw'}`}>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium">{item.logistics_name || '未知物流'}</span>
            {(item?.is_smart || item?.logistics_name?.includes('Smart')) && (
              <Badge variant="outline" className="text-amber-500 border-amber-400 h-5 px-1 py-0 text-[10px]">Smart</Badge>
            )}
          </div>
          <span className="text-xs text-muted-foreground">{title.includes('陆') ? '陆运' : '空运'}</span>
        </div>

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

        {item.breakdown?.length > 0 && (
          <Suspense fallback={<Skeleton className="h-64 w-full" />}>
            <CostPieChart breakdown={item.breakdown} totalPrice={item.price_cny} netProfit={item.profit_cny} />
          </Suspense>
        )}

        <div className="space-y-2">
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

function PrioritySection({ title, data }) {
  return (
    <div>
      <h4 className={`text-sm font-semibold mb-2 ${title.includes('低价') ? 'text-cost-logistics' : 'text-cost-profit'}`}>{title}</h4>
      <div className="grid grid-cols-2 gap-4">
        <ResultCard title="陆运方案" item={data?.land} />
        <ResultCard title="空运方案" item={data?.air} />
      </div>
    </div>
  )
}

function GroupContent({ groupedData, emptyText = '无匹配物流规则' }) {
  if (!groupedData) {
    return <p className="text-sm text-muted-foreground py-4">{emptyText}</p>
  }

  return (
    <div className="space-y-4">
      <PrioritySection title="💰 低价优先" data={groupedData.price_priority} />
      <PrioritySection title="⚡ 速度优先" data={groupedData.speed_priority} />
    </div>
  )
}

function GroupedResultTabs({ groupedResult, groupActiveTab, setGroupActiveTab, cisActiveTab, setCisActiveTab, showBreakeven }) {
  return (
    <Card className="border-cost-profit/20 bg-card/50">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">分组计算结果</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={groupActiveTab} onValueChange={setGroupActiveTab}>
          <TabsList className="grid grid-cols-4 mb-4">
            <TabsTrigger value="rfbs_ru">rFBS-俄罗斯</TabsTrigger>
            <TabsTrigger value="rfbs_cis">rFBS-独联体</TabsTrigger>
            <TabsTrigger value="fbp_ru">FBP-仅俄罗斯</TabsTrigger>
            <TabsTrigger value="fbp_cis">FBP-俄+CIS</TabsTrigger>
          </TabsList>

          <TabsContent value="rfbs_ru" className="mt-0">
            <GroupContent groupedData={getGroupedData(groupedResult, 'rfbs_ru', showBreakeven)} />
          </TabsContent>

          <TabsContent value="rfbs_cis" className="mt-0">
            <Tabs value={cisActiveTab} onValueChange={setCisActiveTab}>
              <TabsList className="grid grid-cols-7 mb-4">
                {CIS_COUNTRIES.map((country) => (
                  <TabsTrigger key={country.key} value={country.key}>{country.label}</TabsTrigger>
                ))}
              </TabsList>
              {CIS_COUNTRIES.map((country) => {
                const groupedData = getGroupedData(groupedResult, country.key, showBreakeven)
                const hasAvailable = groupedData && (
                  groupedData.price_priority?.land?.is_available
                  || groupedData.price_priority?.air?.is_available
                  || groupedData.speed_priority?.land?.is_available
                  || groupedData.speed_priority?.air?.is_available
                )

                return (
                  <TabsContent key={country.key} value={country.key} className="mt-0">
                    {hasAvailable ? <GroupContent groupedData={groupedData} /> : <p className="text-sm text-muted-foreground py-4">该国家无匹配物流规则</p>}
                  </TabsContent>
                )
              })}
            </Tabs>
          </TabsContent>

          <TabsContent value="fbp_ru" className="mt-0">
            <GroupContent groupedData={getGroupedData(groupedResult, 'fbp_ru', showBreakeven)} />
          </TabsContent>

          <TabsContent value="fbp_cis" className="mt-0">
            <GroupContent groupedData={getGroupedData(groupedResult, 'fbp_cis', showBreakeven)} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function FilteredLogisticsPanel({ logistics }) {
  if (!logistics) return null

  const landCount = (logistics.land || []).length
  const airCount = (logistics.air || []).length
  if (landCount + airCount === 0) return null

  return (
    <Collapsible defaultOpen={false}>
      <div className="bg-surface-highest/50 rounded-lg">
        <CollapsibleTrigger className="group flex w-full items-center justify-between p-5 hover:bg-surface-highest/80 rounded-lg transition-colors cursor-pointer">
          <h3 className="text-lg font-semibold text-gray-400">
            被淘汰的物流
            <span className="ml-2 text-sm font-normal text-muted-foreground">({landCount + airCount} 条)</span>
          </h3>
          <ChevronDown className="h-5 w-5 text-gray-400 transition-transform duration-200 group-data-[state=open]:rotate-180" />
        </CollapsibleTrigger>
        <CollapsibleContent className="px-5 pb-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {['land', 'air'].map((type) => (
              <div key={type}>
                <h4 className="text-sm font-medium mb-2 text-gray-500">{type === 'land' ? '🚛 陆运' : '✈️ 空运'}</h4>
                {(logistics[type] || []).length > 0 ? (
                  <div className="space-y-2">
                    {logistics[type].map((item) => {
                      const reason = item.reason || '未提供原因'
                      const isUnselected = reason.includes('未被选中')

                      return (
                        <div key={`${type}-${item.name}`} className={`rounded px-3 py-2 text-sm border ${isUnselected ? 'bg-primary/10 border-primary/20' : 'bg-status-error/10 border-status-error/20'}`}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium">{item.name}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${isUnselected ? 'bg-primary/20 text-primary' : 'bg-status-error/20 text-status-error'}`}>
                              {isUnselected ? '备选' : '淘汰'}
                            </span>
                          </div>
                          <div className="text-muted-foreground text-xs">{reason}</div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground py-2">无</p>
                )}
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}

export default function PricingResultPanel({
  activeTab,
  fastResult,
  preciseResult,
  groupedResult,
  groupActiveTab,
  setGroupActiveTab,
  cisActiveTab,
  setCisActiveTab,
  showBreakeven,
  setShowBreakeven,
}) {
  const result = activeTab === 'fast' ? fastResult : preciseResult
  if (!result && !groupedResult) return null

  const hasPreciseResults = activeTab === 'precise' && (preciseResult || groupedResult)
  const filteredLogistics = getActiveFilteredLogistics({ activeTab, result, groupedResult, groupActiveTab, cisActiveTab })

  return (
    <div className="mt-6 space-y-6">
      <div className="text-sm text-muted-foreground">
        汇率：1 RUB = {result?.exchange_rates?.rub_cny || groupedResult?.exchange_rates?.rub_cny} CNY | 1 USD = {result?.exchange_rates?.usd_cny || groupedResult?.exchange_rates?.usd_cny} CNY
      </div>

      {hasPreciseResults && (
        <div className="flex items-center justify-between bg-muted/40 p-4 rounded-xl border border-border/50 mb-6">
          <div className="space-y-1">
            <Label className="text-sm font-semibold cursor-pointer" onClick={() => setShowBreakeven(!showBreakeven)}>
              盈亏平衡线模式
            </Label>
            <div className="text-xs text-muted-foreground">开启后将展示各项物流方案的盈亏平衡建议售价</div>
          </div>
          <Switch
            aria-label="盈亏平衡线切换"
            checked={showBreakeven}
            onCheckedChange={setShowBreakeven}
            disabled={!preciseResult && !groupedResult}
          />
        </div>
      )}

      {activeTab === 'precise' && groupedResult && (
        <GroupedResultTabs
          groupedResult={groupedResult}
          groupActiveTab={groupActiveTab}
          setGroupActiveTab={setGroupActiveTab}
          cisActiveTab={cisActiveTab}
          setCisActiveTab={setCisActiveTab}
          showBreakeven={showBreakeven}
        />
      )}

      {activeTab === 'fast' && result?.price_priority && (
        <div className="bg-cost-logistics/5 p-4 rounded">
          <h3 className="text-lg font-semibold mb-3">价格优先方案</h3>
          <div className="grid grid-cols-2 gap-3">
            <ResultCard title="🚛 陆运" item={result.price_priority?.land} />
            <ResultCard title="✈️ 空运" item={result.price_priority?.air} />
          </div>
        </div>
      )}

      {activeTab === 'fast' && result?.speed_priority && (
        <div className="bg-cost-profit/5 p-4 rounded">
          <h3 className="text-lg font-semibold mb-3">速度优先方案</h3>
          <div className="grid grid-cols-2 gap-3">
            <ResultCard title="🚛 陆运" item={result.speed_priority?.land} />
            <ResultCard title="✈️ 空运" item={result.speed_priority?.air} />
          </div>
        </div>
      )}

      <FilteredLogisticsPanel logistics={filteredLogistics} />
    </div>
  )
}
