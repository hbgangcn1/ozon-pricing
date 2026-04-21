import React from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { RadioGroup, RadioGroupItem } from '../../components/ui/radio-group'
import { Checkbox } from '../../components/ui/checkbox'
import { Settings2 } from 'lucide-react'
import RateInput from './RateInput'

function PrecisePricingForm({
  preciseForm,
  setPreciseForm,
  commissionCategories,
  handleSavePreciseProduct,
  handlePreciseCalculate,
  loading,
  setProductListDialogOpen
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>物流定价（精准模式）</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* 产品基本信息 */}
        <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
          <Label className="text-sm font-semibold text-foreground">产品基本信息</Label>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">选择产品</Label>
              <Select value={preciseForm.product_id} onValueChange={(v) => {
                if (!v || v === '__clear__') {
                  setPreciseForm({ ...preciseForm, product_id: '', name: '', unit_price: '' })
                } else {
                  // This would need to be handled by parent, but for now placeholder
                  setPreciseForm({ ...preciseForm, product_id: v })
                }
              }}>
                <SelectTrigger className="h-8">
                  <SelectValue placeholder="从列表选择..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__clear__">清除选择</SelectItem>
                  {/* products would be passed as prop */}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end gap-2">
              <Button size="sm" onClick={() => setProductListDialogOpen(true)} className="h-8 transition-all duration-200">打开产品列表</Button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">产品名称 <span className="text-status-error">*</span></Label>
              <Input value={preciseForm.name}
                onChange={(e) => setPreciseForm({ ...preciseForm, name: e.target.value })}
                placeholder="必填" className="h-8" />
            </div>
            <RateInput label="进货单价（元）" value={preciseForm.unit_price}
              onChange={(v) => setPreciseForm({ ...preciseForm, unit_price: v })} defaultVal="0" step="0.01" />
          </div>
        </div>

        {/* 物流规格 */}
        <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
          <Label className="text-sm font-semibold text-foreground">物流规格</Label>
          <div className="grid grid-cols-2 gap-3">
            <RateInput label="商品重量（克）" value={preciseForm.weight_g}
              onChange={(v) => setPreciseForm({ ...preciseForm, weight_g: v })} defaultVal="0" />
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">包装类型</Label>
            <RadioGroup
              value={preciseForm.is_cylinder}
              onValueChange={(v) => setPreciseForm({ ...preciseForm, is_cylinder: v })}
              className="flex gap-4"
            >
              <div className="flex items-center gap-1.5">
                <RadioGroupItem value="regular" id="pkg-regular" />
                <Label htmlFor="pkg-regular" className="text-sm cursor-pointer">常规包装</Label>
              </div>
              <div className="flex items-center gap-1.5">
                <RadioGroupItem value="cylinder" id="pkg-cylinder" />
                <Label htmlFor="pkg-cylinder" className="text-sm cursor-pointer">圆柱包装</Label>
              </div>
            </RadioGroup>
          </div>
          {preciseForm.is_cylinder === 'regular' ? (
            <div className="grid grid-cols-3 gap-3">
              <RateInput label="长度（厘米）" value={preciseForm.length_cm}
                onChange={(v) => setPreciseForm({ ...preciseForm, length_cm: v })} defaultVal="0" />
              <RateInput label="宽度（厘米）" value={preciseForm.width_cm}
                onChange={(v) => setPreciseForm({ ...preciseForm, width_cm: v })} defaultVal="0" />
              <RateInput label="高度（厘米）" value={preciseForm.height_cm}
                onChange={(v) => setPreciseForm({ ...preciseForm, height_cm: v })} defaultVal="0" />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <RateInput label="圆柱直径（厘米）" value={preciseForm.cylinder_diameter}
                onChange={(v) => setPreciseForm({ ...preciseForm, cylinder_diameter: v })} defaultVal="0" />
              <RateInput label="圆柱长度（厘米）" value={preciseForm.cylinder_length}
                onChange={(v) => setPreciseForm({ ...preciseForm, cylinder_length: v })} defaultVal="0" />
            </div>
          )}
        </div>

        {/* 电池和液体 */}
        <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
          <Label className="text-sm font-semibold text-foreground">电池和液体</Label>
          <div className="flex gap-4 flex-wrap">
            <div className="flex items-center gap-2 text-sm">
              <Checkbox checked={preciseForm.has_battery}
                aria-label="含电池"
                onCheckedChange={(v) => setPreciseForm({ ...preciseForm, has_battery: !!v })} />
              含电池
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Checkbox checked={preciseForm.has_liquid}
                aria-label="含液体"
                onCheckedChange={(v) => setPreciseForm({ ...preciseForm, has_liquid: !!v })} />
              含液体
            </div>
          </div>
        </div>

        {/* 定价参数 */}
        <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
          <Label className="text-sm font-semibold text-foreground">定价参数</Label>
          <div className="grid grid-cols-2 gap-3">
            <RateInput label="贴标费用（元）" value={preciseForm.labeling_fee}
              onChange={(v) => setPreciseForm({ ...preciseForm, labeling_fee: v })} defaultVal="0" step="0.01" />

            <RateInput label="供货方不包邮运费（元）" value={preciseForm.shipping_fee}
              onChange={(v) => setPreciseForm({ ...preciseForm, shipping_fee: v })} defaultVal="0" step="0.01" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">佣金类目</Label>
              <div className="flex items-center gap-2">
                <Select value={preciseForm.commission_category_id} onValueChange={(v) => setPreciseForm({ ...preciseForm, commission_category_id: v })}>
                  <SelectTrigger className="h-8 flex-1">
                    <SelectValue placeholder="选择佣金类目" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">不使用类目(0%)</SelectItem>
                    {commissionCategories.map(cat => (
                      <SelectItem key={cat.id} value={String(cat.id)}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" size="sm" className="h-8 px-3 text-xs bg-muted/50 hover:bg-muted transition-colors" onClick={() => window.open('/commission-categories', '_blank')}>
                  <Settings2 className="w-3.5 h-3.5 mr-1" />
                  管理
                </Button>
              </div>
            </div>
            <RateInput label="运营利润率(%)" value={preciseForm.target_profit_margin}
              onChange={(v) => setPreciseForm({ ...preciseForm, target_profit_margin: v })} defaultVal="0" step="1" />
            <RateInput label="推广费率(%)" value={preciseForm.promotion_cost_rate}
              onChange={(v) => setPreciseForm({ ...preciseForm, promotion_cost_rate: v })} defaultVal="0" step="1" />
            <RateInput label="打款提现费率(%)" value={preciseForm.withdrawal_fee_rate}
              onChange={(v) => setPreciseForm({ ...preciseForm, withdrawal_fee_rate: v })} defaultVal="0" step="1" />
            <RateInput label="收单手续费率(%)" value={preciseForm.payment_processing_fee}
              onChange={(v) => setPreciseForm({ ...preciseForm, payment_processing_fee: v })} defaultVal="0" step="1" />
            <RateInput label="历史退货率(%)" value={preciseForm.return_rate}
              onChange={(v) => setPreciseForm({ ...preciseForm, return_rate: v })} defaultVal="0" step="1" />
            <RateInput label="增值税率(%)" value={preciseForm.vat_rate}
              onChange={(v) => setPreciseForm({ ...preciseForm, vat_rate: v })} defaultVal="0" step="1" />
          </div>
        </div>

        <div className="flex gap-3">
          <Button onClick={handleSavePreciseProduct} className="flex-1 transition-all duration-200">保存产品</Button>
          <Button onClick={handlePreciseCalculate} disabled={loading} className="flex-1 transition-all duration-200">
            {loading ? '计算中...' : '开始计算'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default PrecisePricingForm
