import React from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import RateInput from './RateInput'

function FastPricingForm({ fastForm, setFastForm, handleFastCalculate, loading }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>物流定价（快速模式）</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <RateInput label="进货单价（元）" value={fastForm.unit_price}
            onChange={(v) => setFastForm({ ...fastForm, unit_price: v })} defaultVal="0" />
          <RateInput label="商品重量（克）" value={fastForm.weight_g}
            onChange={(v) => setFastForm({ ...fastForm, weight_g: v })} defaultVal="0" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <RateInput label="佣金费率(%)" value={fastForm.commission_rate}
            onChange={(v) => setFastForm({ ...fastForm, commission_rate: v })} defaultVal="0" step="1" />
          <RateInput label="运营利润率(%)" value={fastForm.target_profit_margin}
            onChange={(v) => setFastForm({ ...fastForm, target_profit_margin: v })} defaultVal="0" step="1" />
          <RateInput label="推广费率(%)" value={fastForm.promotion_cost_rate}
            onChange={(v) => setFastForm({ ...fastForm, promotion_cost_rate: v })} defaultVal="0" step="1" />
          <RateInput label="打款提现费率(%)" value={fastForm.withdrawal_fee_rate}
            onChange={(v) => setFastForm({ ...fastForm, withdrawal_fee_rate: v })} defaultVal="0" step="1" />
          <RateInput label="收单手续费率(%)" value={fastForm.payment_processing_fee}
            onChange={(v) => setFastForm({ ...fastForm, payment_processing_fee: v })} defaultVal="0" step="1" />
          <RateInput label="历史退货率(%)" value={fastForm.return_rate}
            onChange={(v) => setFastForm({ ...fastForm, return_rate: v })} defaultVal="0" step="1" />
          <RateInput label="增值税率(%)" value={fastForm.vat_rate}
            onChange={(v) => setFastForm({ ...fastForm, vat_rate: v })} defaultVal="0" step="1" />
        </div>

        <Button onClick={handleFastCalculate} disabled={loading} className="w-full transition-all duration-200">
          {loading ? '计算中...' : '开始计算'}
        </Button>
      </CardContent>
    </Card>
  )
}

export default FastPricingForm
