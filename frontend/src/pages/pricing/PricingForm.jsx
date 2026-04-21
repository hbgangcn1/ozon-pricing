import React from 'react'
import { Settings2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Checkbox } from '../../components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '../../components/ui/radio-group'
import RateInput from './RateInput'

function openCommissionCategories() {
  window.open('/commission-categories', '_blank')
}

function ProductDimensionFields({ form, setForm }) {
  if (form.is_cylinder === 'regular') {
    return (
      <div className="grid grid-cols-3 gap-3">
        <RateInput label="长度（厘米）" value={form.length_cm} onChange={(value) => setForm({ ...form, length_cm: value })} defaultVal="0" />
        <RateInput label="宽度（厘米）" value={form.width_cm} onChange={(value) => setForm({ ...form, width_cm: value })} defaultVal="0" />
        <RateInput label="高度（厘米）" value={form.height_cm} onChange={(value) => setForm({ ...form, height_cm: value })} defaultVal="0" />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      <RateInput label="圆柱直径（厘米）" value={form.cylinder_diameter} onChange={(value) => setForm({ ...form, cylinder_diameter: value })} defaultVal="0" />
      <RateInput label="圆柱长度（厘米）" value={form.cylinder_length} onChange={(value) => setForm({ ...form, cylinder_length: value })} defaultVal="0" />
    </div>
  )
}

function PrecisePricingFields({ preciseForm, setPreciseForm, commissionCategories }) {
  return (
    <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
      <Label className="text-sm font-semibold text-foreground">定价参数</Label>
      <div className="grid grid-cols-2 gap-3">
        <RateInput label="贴标费用（元）" value={preciseForm.labeling_fee} onChange={(value) => setPreciseForm({ ...preciseForm, labeling_fee: value })} defaultVal="0" step="0.01" />
        <RateInput label="供货方不包邮运费（元）" value={preciseForm.shipping_fee} onChange={(value) => setPreciseForm({ ...preciseForm, shipping_fee: value })} defaultVal="0" step="0.01" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">佣金类目</Label>
          <div className="flex items-center gap-2">
            <Select value={preciseForm.commission_category_id} onValueChange={(value) => setPreciseForm({ ...preciseForm, commission_category_id: value })}>
              <SelectTrigger className="h-8 flex-1">
                <SelectValue placeholder="选择佣金类目" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">不使用类目(0%)</SelectItem>
                {commissionCategories.map((category) => (
                  <SelectItem key={category.id} value={String(category.id)}>{category.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" className="h-8 px-3 text-xs bg-muted/50 hover:bg-muted transition-colors" onClick={openCommissionCategories}>
              <Settings2 className="w-3.5 h-3.5 mr-1" />
              管理
            </Button>
          </div>
        </div>
        <RateInput label="运营利润率(%)" value={preciseForm.target_profit_margin} onChange={(value) => setPreciseForm({ ...preciseForm, target_profit_margin: value })} defaultVal="0" step="1" />
        <RateInput label="推广费率(%)" value={preciseForm.promotion_cost_rate} onChange={(value) => setPreciseForm({ ...preciseForm, promotion_cost_rate: value })} defaultVal="0" step="1" />
        <RateInput label="打款提现费率(%)" value={preciseForm.withdrawal_fee_rate} onChange={(value) => setPreciseForm({ ...preciseForm, withdrawal_fee_rate: value })} defaultVal="0" step="1" />
        <RateInput label="收单手续费率(%)" value={preciseForm.payment_processing_fee} onChange={(value) => setPreciseForm({ ...preciseForm, payment_processing_fee: value })} defaultVal="0" step="1" />
        <RateInput label="历史退货率(%)" value={preciseForm.return_rate} onChange={(value) => setPreciseForm({ ...preciseForm, return_rate: value })} defaultVal="0" step="1" />
        <RateInput label="增值税率(%)" value={preciseForm.vat_rate} onChange={(value) => setPreciseForm({ ...preciseForm, vat_rate: value })} defaultVal="0" step="1" />
      </div>
    </div>
  )
}

export default function PricingForm({
  activeTab,
  setActiveTab,
  preciseLabel,
  fastForm,
  setFastForm,
  preciseForm,
  setPreciseForm,
  products,
  commissionCategories,
  loading,
  onOpenProductList,
  onProductSelect,
  onSavePreciseProduct,
  onFastCalculate,
  onPreciseCalculate,
}) {
  return (
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <TabsList className="mb-4 grid grid-cols-2 w-full">
        <TabsTrigger value="fast">快速模式</TabsTrigger>
        <TabsTrigger value="precise">{preciseLabel}</TabsTrigger>
      </TabsList>

      <TabsContent value="fast">
        <Card>
          <CardHeader>
            <CardTitle>物流定价（快速模式）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <RateInput label="进货单价（元）" value={fastForm.unit_price} onChange={(value) => setFastForm({ ...fastForm, unit_price: value })} defaultVal="0" />
              <RateInput label="商品重量（克）" value={fastForm.weight_g} onChange={(value) => setFastForm({ ...fastForm, weight_g: value })} defaultVal="0" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <RateInput label="佣金费率(%)" value={fastForm.commission_rate} onChange={(value) => setFastForm({ ...fastForm, commission_rate: value })} defaultVal="0" step="1" />
              <RateInput label="运营利润率(%)" value={fastForm.target_profit_margin} onChange={(value) => setFastForm({ ...fastForm, target_profit_margin: value })} defaultVal="0" step="1" />
              <RateInput label="推广费率(%)" value={fastForm.promotion_cost_rate} onChange={(value) => setFastForm({ ...fastForm, promotion_cost_rate: value })} defaultVal="0" step="1" />
              <RateInput label="打款提现费率(%)" value={fastForm.withdrawal_fee_rate} onChange={(value) => setFastForm({ ...fastForm, withdrawal_fee_rate: value })} defaultVal="0" step="1" />
              <RateInput label="收单手续费率(%)" value={fastForm.payment_processing_fee} onChange={(value) => setFastForm({ ...fastForm, payment_processing_fee: value })} defaultVal="0" step="1" />
              <RateInput label="历史退货率(%)" value={fastForm.return_rate} onChange={(value) => setFastForm({ ...fastForm, return_rate: value })} defaultVal="0" step="1" />
              <RateInput label="增值税率(%)" value={fastForm.vat_rate} onChange={(value) => setFastForm({ ...fastForm, vat_rate: value })} defaultVal="0" step="1" />
            </div>

            <Button onClick={onFastCalculate} disabled={loading} className="w-full transition-all duration-200">
              {loading ? '计算中...' : '开始计算'}
            </Button>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="precise">
        <Card>
          <CardHeader>
            <CardTitle>物流定价（精准模式）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
              <Label className="text-sm font-semibold text-foreground">产品基本信息</Label>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">选择产品</Label>
                  <Select value={preciseForm.product_id} onValueChange={onProductSelect}>
                    <SelectTrigger className="h-8">
                      <SelectValue placeholder="从列表选择..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__clear__">清除选择</SelectItem>
                      {products.map((product) => (
                        <SelectItem key={product.id} value={String(product.id)}>{product.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end gap-2">
                  <Button size="sm" onClick={onOpenProductList} className="h-8 transition-all duration-200">打开产品列表</Button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">产品名称 <span className="text-status-error">*</span></Label>
                  <Input value={preciseForm.name} onChange={(event) => setPreciseForm({ ...preciseForm, name: event.target.value })} placeholder="必填" className="h-8" />
                </div>
                <RateInput label="进货单价（元）" value={preciseForm.unit_price} onChange={(value) => setPreciseForm({ ...preciseForm, unit_price: value })} defaultVal="0" step="0.01" />
              </div>
            </div>

            <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
              <Label className="text-sm font-semibold text-foreground">物流规格</Label>
              <div className="grid grid-cols-2 gap-3">
                <RateInput label="商品重量（克）" value={preciseForm.weight_g} onChange={(value) => setPreciseForm({ ...preciseForm, weight_g: value })} defaultVal="0" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">包装类型</Label>
                <RadioGroup value={preciseForm.is_cylinder} onValueChange={(value) => setPreciseForm({ ...preciseForm, is_cylinder: value })} className="flex gap-4">
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
              <ProductDimensionFields form={preciseForm} setForm={setPreciseForm} />
            </div>

            <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border/50">
              <Label className="text-sm font-semibold text-foreground">电池和液体</Label>
              <div className="flex gap-4 flex-wrap">
                <div className="flex items-center gap-2 text-sm">
                  <Checkbox checked={preciseForm.has_battery} aria-label="含电池" onCheckedChange={(value) => setPreciseForm({ ...preciseForm, has_battery: !!value })} />
                  含电池
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Checkbox checked={preciseForm.has_liquid} aria-label="含液体" onCheckedChange={(value) => setPreciseForm({ ...preciseForm, has_liquid: !!value })} />
                  含液体
                </div>
              </div>
            </div>

            <PrecisePricingFields preciseForm={preciseForm} setPreciseForm={setPreciseForm} commissionCategories={commissionCategories} />

            <div className="flex gap-3">
              <Button onClick={onSavePreciseProduct} className="flex-1 transition-all duration-200">保存产品</Button>
              <Button onClick={onPreciseCalculate} disabled={loading} className="flex-1 transition-all duration-200">
                {loading ? '计算中...' : '开始计算'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  )
}
