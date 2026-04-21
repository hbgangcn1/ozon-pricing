import React from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs'
import { Label } from '../../components/ui/label'
import { Switch } from '../../components/ui/switch'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../../components/ui/collapsible'
import { ChevronDown } from 'lucide-react'
import ResultCard from './ResultCard'
import { CIS_COUNTRIES } from './pricingConstants'

function PricingResult({
  activeTab,
  fastResult,
  preciseResult,
  groupedResult,
  groupActiveTab,
  setGroupActiveTab,
  cisActiveTab,
  setCisActiveTab,
  showBreakeven,
  setShowBreakeven
}) {
  const result = activeTab === 'fast' ? fastResult : preciseResult
  if (!result && !groupedResult) return null
  const hasPreciseResults = activeTab === 'precise' && (preciseResult || groupedResult)
  const pp = result?.price_priority
  const sp = result?.speed_priority
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
              {/* rFBS-俄罗斯 */}
              <TabsContent value="rfbs_ru" className="mt-0">
                {(() => {
                  const dk = showBreakeven ? 'breakeven_rfbs_ru' : 'rfbs_ru'
                  const gd = groupedResult[dk] || groupedResult['rfbs_ru']
                  if (!gd) return <p className="text-sm text-muted-foreground py-4">无匹配物流规则</p>
                  return (
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-cost-logistics mb-2">💰 低价优先</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <ResultCard title="陆运方案" item={gd.price_priority?.land} />
                          <ResultCard title="空运方案" item={gd.price_priority?.air} />
                        </div>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-cost-profit mb-2">⚡ 速度优先</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <ResultCard title="陆运方案" item={gd.speed_priority?.land} />
                          <ResultCard title="空运方案" item={gd.speed_priority?.air} />
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </TabsContent>
              {/* rFBS-独联体 — 6 country sub-tabs */}
              <TabsContent value="rfbs_cis" className="mt-0">
                <Tabs value={cisActiveTab} onValueChange={setCisActiveTab}>
                  <TabsList className="grid grid-cols-6 mb-4">
                    {CIS_COUNTRIES.map(c => (
                      <TabsTrigger key={c.key} value={c.key}>{c.label}</TabsTrigger>
                    ))}
                  </TabsList>
                  {CIS_COUNTRIES.map(c => {
                    const dk = showBreakeven ? `breakeven_${c.key}` : c.key
                    const gd = groupedResult[dk] || groupedResult[c.key]
                    return (
                      <TabsContent key={c.key} value={c.key} className="mt-0">
                        {gd && (gd.price_priority?.land?.is_available || gd.price_priority?.air?.is_available || gd.speed_priority?.land?.is_available || gd.speed_priority?.air?.is_available) ? (
                          <div className="space-y-4">
                            <div>
                              <h4 className="text-sm font-semibold text-cost-logistics mb-2">💰 低价优先</h4>
                              <div className="grid grid-cols-2 gap-4">
                                <ResultCard title="陆运方案" item={gd.price_priority?.land} />
                                <ResultCard title="空运方案" item={gd.price_priority?.air} />
                              </div>
                            </div>
                            <div>
                              <h4 className="text-sm font-semibold text-cost-profit mb-2">⚡ 速度优先</h4>
                              <div className="grid grid-cols-2 gap-4">
                                <ResultCard title="陆运方案" item={gd.speed_priority?.land} />
                                <ResultCard title="空运方案" item={gd.speed_priority?.air} />
                              </div>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground py-4">该国家无匹配物流规则</p>
                        )}
                      </TabsContent>
                    )
                  })}
                </Tabs>
              </TabsContent>
              {/* FBP-仅俄罗斯 */}
              <TabsContent value="fbp_ru" className="mt-0">
                {(() => {
                  const dk = showBreakeven ? 'breakeven_fbp_ru' : 'fbp_ru'
                  const gd = groupedResult[dk] || groupedResult['fbp_ru']
                  if (!gd) return <p className="text-sm text-muted-foreground py-4">无匹配物流规则</p>
                  return (
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-cost-logistics mb-2">💰 低价优先</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <ResultCard title="陆运方案" item={gd.price_priority?.land} />
                          <ResultCard title="空运方案" item={gd.price_priority?.air} />
                        </div>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-cost-profit mb-2">⚡ 速度优先</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <ResultCard title="陆运方案" item={gd.speed_priority?.land} />
                          <ResultCard title="空运方案" item={gd.speed_priority?.air} />
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </TabsContent>
              {/* FBP-俄+CIS */}
              <TabsContent value="fbp_cis" className="mt-0">
                {(() => {
                  const dk = showBreakeven ? 'breakeven_fbp_cis' : 'fbp_cis'
                  const gd = groupedResult[dk] || groupedResult['fbp_cis']
                  if (!gd) return <p className="text-sm text-muted-foreground py-4">无匹配物流规则</p>
                  return (
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-cost-logistics mb-2">💰 低价优先</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <ResultCard title="陆运方案" item={gd.price_priority?.land} />
                          <ResultCard title="空运方案" item={gd.price_priority?.air} />
                        </div>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-cost-profit mb-2">⚡ 速度优先</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <ResultCard title="陆运方案" item={gd.speed_priority?.land} />
                          <ResultCard title="空运方案" item={gd.speed_priority?.air} />
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {/* 价格优先方案 — 仅快速模式 */}
      {activeTab === 'fast' && pp && (
      <div className="bg-cost-logistics/5 p-4 rounded">
        <h3 className="text-lg font-semibold mb-3">价格优先方案</h3>
        <div className="grid grid-cols-2 gap-3">
          <ResultCard title="🚛 陆运" item={pp?.land} />
          <ResultCard title="✈️ 空运" item={pp?.air} />
        </div>
      </div>
      )}

      {/* 速度优先方案 — 仅快速模式 */}
      {activeTab === 'fast' && sp && (
      <div className="bg-cost-profit/5 p-4 rounded">
        <h3 className="text-lg font-semibold mb-3">速度优先方案</h3>
        <div className="grid grid-cols-2 gap-3">
          <ResultCard title="🚛 陆运" item={sp?.land} />
          <ResultCard title="✈️ 空运" item={sp?.air} />
        </div>
      </div>
      )}

      {/* 被淘汰的物流 */}
      {(() => {
        const fl = activeTab === 'precise' && groupedResult
          ? (groupActiveTab === 'rfbs_cis'
            ? groupedResult[cisActiveTab]?.filtered_logistics
            : groupedResult[groupActiveTab]?.filtered_logistics)
          : result?.filtered_logistics
        if (!fl) return null
        const landCount = (fl.land || []).length
        const airCount = (fl.air || []).length
        if (landCount + airCount === 0) return null
        return (
        <Collapsible defaultOpen={false}>
          <div className="bg-surface-highest/50 rounded-lg">
            <CollapsibleTrigger className="group flex w-full items-center justify-between p-5 hover:bg-surface-highest/80 rounded-lg transition-colors cursor-pointer">
              <h3 className="text-lg font-semibold text-gray-400">
                被淘汰的物流
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  ({landCount + airCount} 条)
                </span>
              </h3>
              <ChevronDown className="h-5 w-5 text-gray-400 transition-transform duration-200 group-data-[state=open]:rotate-180" />
            </CollapsibleTrigger>
            <CollapsibleContent className="px-5 pb-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {['land', 'air'].map(type => (
                  <div key={type}>
                    <h4 className="text-sm font-medium mb-2 text-gray-500">{type === 'land' ? '🚛 陆运' : '✈️ 空运'}</h4>
                    {(fl[type] || []).length > 0 ? (
                      <div className="space-y-2">
                          {fl[type].map((item) => {
                            const isUnselected = item.reason.includes('未被选中');
                            return (
                              <div key={`${type}-${item.name}`} className={`rounded px-3 py-2 text-sm border ${
                                isUnselected
                                  ? 'bg-primary/10 border-primary/20'
                                  : 'bg-status-error/10 border-status-error/20'
                              }`}>
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-medium">{item.name}</span>
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                                    isUnselected
                                      ? 'bg-primary/20 text-primary'
                                      : 'bg-status-error/20 text-status-error'
                                  }`}>
                                    {isUnselected ? '备选' : '淘汰'}
                                  </span>
                                </div>
                                <div className="text-muted-foreground text-xs">{item.reason}</div>
                              </div>
                            );
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
      })()}
    </div>
  )
}

export default PricingResult
