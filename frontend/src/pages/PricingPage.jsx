import React, { useEffect, useState, useRef } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { Checkbox } from '../components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog'
import { toast } from 'sonner'
import { pricingAPI, productsAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import CostPieChart from '../components/charts/CostPieChart'

// 安全提取 API 错误信息，避免将对象渲染到 React toast
const getApiError = (error) => {
  try {
    const detail = error?.response?.data?.detail
    if (!detail) return null
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail[0]?.msg || detail[0]?.message || String(detail[0])
    }
    if (typeof detail === 'object') {
      return detail?.msg || detail?.message || JSON.stringify(detail)
    }
    return String(detail)
  } catch {
    return null
  }
}

const DEFAULT_FAST = {
  unit_price: '',
  weight_g: '',
  commission_rate: '0',
  target_profit_margin: '0',
  promotion_cost_rate: '0',
  withdrawal_fee_rate: '0',
  payment_processing_fee: '0',
  return_rate: '0',
  vat_rate: '0',
}

const DEFAULT_PRECISE = {
  product_id: '',
  name: '',
  unit_price: '',
  labeling_fee: '0',
  shipping_fee: '0',
  weight_g: '',
  length_cm: '',
  width_cm: '',
  height_cm: '',
  is_cylinder: 'regular',
  cylinder_diameter: '',
  cylinder_length: '',
  has_battery: false,
  battery_capacity_wh: '',
  battery_capacity_mah: '',
  battery_voltage: '',
  battery_capacity_type: 'wh',
  has_msds: false,
  has_liquid: false,
  commission_rate: '0',
  target_profit_margin: '0',
  promotion_cost_rate: '0',
  withdrawal_fee_rate: '0',
  payment_processing_fee: '0',
  return_rate: '0',
  vat_rate: '0',
}

function RateInput({ label, value, onChange, defaultVal }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={defaultVal}
        className="h-8"
      />
    </div>
  )
}

function ResultCard({ title, item }) {
  if (!item?.is_available) {
    const emptyTitleClass = title.includes('自提') && title.includes('陆运')
      ? 'bg-[rgba(0,128,128,0.3)] text-teal-300'
      : title.includes('自提') && title.includes('空运')
        ? 'bg-[rgba(30,64,175,0.3)] text-blue-300'
        : title.includes('送货上门') && title.includes('陆运')
          ? 'bg-[rgba(128,0,128,0.3)] text-purple-300'
          : 'bg-[rgba(157,23,114,0.3)] text-fuchsia-300'
    return (
      <Card className="border-dashed">
        <CardContent className="py-3 px-4">
          <div className={`flex justify-between items-center p-2 rounded ${emptyTitleClass}`}>
            <span className="text-sm font-medium">{title}</span>
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
            title.includes('自提') && title.includes('陆运')
              ? 'bg-[rgba(0,128,128,0.3)] text-teal-300'
              : title.includes('自提') && title.includes('空运')
                ? 'bg-[rgba(30,64,175,0.3)] text-blue-300'
                : title.includes('送货上门') && title.includes('陆运')
                  ? 'bg-[rgba(128,0,128,0.3)] text-purple-300'
                  : 'bg-[rgba(157,23,114,0.3)] text-fuchsia-300'
          }`}
        >
          <span className="text-sm font-medium">{title}</span>
          <span className="text-xs">{item.logistics_name}</span>
        </div>

        {/* 售价行 */}
        <div className="flex justify-between items-center">
          <div>
            <span className="text-muted-foreground">建议售价 </span>
            <span className="text-2xl font-bold text-white">¥{item.price_cny?.toFixed(2)}</span>
          </div>
          <div className="text-sm">
            <span className="text-muted-foreground">运营利润率 </span>
            <span className="font-semibold text-green-400">{item.profit_margin_pct?.toFixed(1)}%</span>
          </div>
        </div>

        {/* 饼图行 */}
        {item.breakdown && item.breakdown.length > 0 && (
          <CostPieChart
            breakdown={item.breakdown}
            totalPrice={item.price_cny}
            netProfit={item.profit_cny}
          />
        )}

        {/* 底部3行对比数据 */}
        <div className="space-y-2">
          {/* 第1行：运费与时效 */}
          <div className="flex justify-between bg-[rgba(59,130,246,0.05)] rounded p-1">
            <div className="flex justify-between flex-1 mr-2">
              <span className="text-blue-300">运费</span>
              <span className="text-white font-medium">¥{item.logistics_cost?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between flex-1 ml-2">
              <span className="text-blue-300">时效</span>
              <span className="text-white font-medium">{item.days_min}-{item.days_max}天</span>
            </div>
          </div>

          {/* 第2行：平均运费与节省运费 */}
          <div className="flex justify-between bg-[rgba(34,197,94,0.05)] rounded p-1">
            <div className="flex justify-between flex-1 mr-2">
              <span className="text-blue-300">平均运费</span>
              <span className="text-white font-medium">¥{item.avg_cost?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between flex-1 ml-2">
              <span className="text-blue-300">节省</span>
              <span className="text-white font-medium">{savedCostPct !== null ? `${savedCostPct > 0 ? '+' : ''}${savedCostPct}%` : '-'}</span>
            </div>
          </div>

          {/* 第3行：平均时效与节省时效 */}
          <div className="flex justify-between bg-[rgba(249,115,22,0.05)] rounded p-1">
            <div className="flex justify-between flex-1 mr-2">
              <span className="text-blue-300">平均时效</span>
              <span className="text-white font-medium">{item.avg_days?.toFixed(1)}天</span>
            </div>
            <div className="flex justify-between flex-1 ml-2">
              <span className="text-blue-300">节省</span>
              <span className="text-white font-medium">{item.saved_days != null ? `${item.saved_days > 0 ? '+' : ''}${item.saved_days.toFixed(1)}天` : '-'}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function PricingPage() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('fast')
  const [loading, setLoading] = useState(false)
  const [fastResult, setFastResult] = useState(null)
  const [preciseResult, setPreciseResult] = useState(null)
  const [fastForm, setFastForm] = useState(DEFAULT_FAST)
  const [preciseForm, setPreciseForm] = useState(DEFAULT_PRECISE)
  const [products, setProducts] = useState([])
  const [productDialogOpen, setProductDialogOpen] = useState(false)
  const [productListDialogOpen, setProductListDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [pendingDeleteProduct, setPendingDeleteProduct] = useState(null)
  const [productForm, setProductForm] = useState({
    name: '',
    unit_price: '',
    labeling_fee: '0',
    shipping_fee: '0',
    weight_g: '',
    length_cm: '',
    width_cm: '',
    height_cm: '',
    is_cylinder: 'regular',
    cylinder_diameter: '',
    cylinder_length: '',
    has_battery: false,
    battery_capacity_wh: '',
    battery_capacity_mah: '',
    battery_voltage: '',
    battery_capacity_type: 'wh',
    has_msds: false,
    has_liquid: false,
    commission_rate: '0',
    target_profit_margin: '0',
    promotion_cost_rate: '0',
    withdrawal_fee_rate: '0',
    payment_processing_fee: '0',
    return_rate: '0',
    vat_rate: '0',
  })

  const isPreciseDisabled = user?.user_type === 'free' || user?.user_type === 'efficiency'
  const preciseLabel = isPreciseDisabled ? '精准模式（限专业版/企业版）' : '精准模式'
  const lastCalcToastRef = useRef(0)
  const calcToastShownRef = useRef(false)

  useEffect(() => {
    refreshProducts()
  }, [])

  const refreshProducts = () => {
    productsAPI.getAll().then(data => setProducts(Array.isArray(data) ? data : [])).catch(err => { console.error(err) })
  }

  useEffect(() => {
    if (productListDialogOpen) {
      refreshProducts()
    }
  }, [productListDialogOpen])

  const handleOpenProductDialog = () => {
    setEditingProduct(null)
    setProductForm({
      name: '',
      unit_price: '',
      labeling_fee: '0',
      shipping_fee: '0',
      weight_g: '',
      length_cm: '',
      width_cm: '',
      height_cm: '',
      is_cylinder: 'regular',
      cylinder_diameter: '',
      cylinder_length: '',
      has_battery: false,
      battery_capacity_wh: '',
      battery_capacity_mah: '',
      battery_voltage: '',
      battery_capacity_type: 'wh',
      has_msds: false,
      has_liquid: false,
    })
    setProductDialogOpen(true)
  }

  const handleEditProduct = (product) => {
    setEditingProduct(product)
    setProductForm({
      name: product.name || '',
      unit_price: String(product.unit_price || ''),
      labeling_fee: String(product.labeling_fee || '0'),
      shipping_fee: String(product.shipping_fee || '0'),
      weight_g: String(product.weight_g || ''),
      length_cm: String(product.length_cm || ''),
      width_cm: String(product.width_cm || ''),
      height_cm: String(product.height_cm || ''),
      is_cylinder: product.is_cylinder ? 'cylinder' : 'regular',
      cylinder_diameter: String(product.cylinder_diameter || ''),
      cylinder_length: String(product.cylinder_length || ''),
      has_battery: !!product.has_battery,
      battery_capacity_wh: String(product.battery_capacity_wh || ''),
      battery_capacity_mah: String(product.battery_capacity_mah || ''),
      battery_voltage: String(product.battery_voltage || ''),
      battery_capacity_type: product.battery_capacity_type || 'wh',
      has_msds: !!product.has_msds,
      has_liquid: !!product.has_liquid,
      commission_rate: String(product.commission_rate || '0'),
      target_profit_margin: String(product.target_profit_margin || '0'),
      promotion_cost_rate: String(product.promotion_cost_rate || '0'),
      withdrawal_fee_rate: String(product.withdrawal_fee_rate || '0'),
      payment_processing_fee: String(product.payment_processing_fee || '0'),
      return_rate: String(product.return_rate || '0'),
      vat_rate: String(product.vat_rate || '0'),
    })
    setProductDialogOpen(true)
  }

  const handleSaveProduct = async () => {
    if (!productForm.name || !productForm.unit_price || !productForm.weight_g) {
      toast.error('请填写名称、进货单价和重量')
      return
    }
    // 重量不能为0
    if (Number(productForm.weight_g) <= 0) {
      toast.error('商品重量不能为 0')
      return
    }
    // 尺寸校验（常规包装时）
    if (productForm.is_cylinder === 'regular') {
      if (Number(productForm.length_cm) <= 0) {
        toast.error('长度不能为 0')
        return
      }
      if (Number(productForm.width_cm) <= 0) {
        toast.error('宽度不能为 0')
        return
      }
      if (Number(productForm.height_cm) <= 0) {
        toast.error('高度不能为 0')
        return
      }
    }
    // 圆柱包装尺寸校验
    if (productForm.is_cylinder === 'cylinder') {
      if (Number(productForm.cylinder_diameter) <= 0) {
        toast.error('圆柱直径不能为 0')
        return
      }
      if (Number(productForm.cylinder_length) <= 0) {
        toast.error('圆柱长度不能为 0')
        return
      }
    }
    // 重名检查
    const isDuplicate = products.some(p => {
      if (editingProduct && p.id === editingProduct.id) return false
      return p.name === productForm.name
    })
    if (isDuplicate) {
      toast.error('存在重名产品')
      return
    }
    try {
      const isCylinder = productForm.is_cylinder === 'cylinder'
      const data = {
        name: productForm.name,
        unit_price: Number(productForm.unit_price),
        labeling_fee: Number(productForm.labeling_fee) || 0,
        shipping_fee: Number(productForm.shipping_fee) || 0,
        weight_g: Number(productForm.weight_g),
        length_cm: isCylinder ? 0 : (Number(productForm.length_cm) || 0),
        width_cm: isCylinder ? 0 : (Number(productForm.width_cm) || 0),
        height_cm: isCylinder ? 0 : (Number(productForm.height_cm) || 0),
        is_cylinder: isCylinder,
        cylinder_diameter: isCylinder ? (Number(productForm.cylinder_diameter) || 0) : 0,
        cylinder_length: isCylinder ? (Number(productForm.cylinder_length) || 0) : 0,
        has_battery: productForm.has_battery,
        battery_capacity_wh: Number(productForm.battery_capacity_wh) || 0,
        battery_capacity_mah: Number(productForm.battery_capacity_mah) || 0,
        battery_voltage: Number(productForm.battery_voltage) || 0,
        battery_capacity_type: productForm.battery_capacity_type || 'wh',
        has_msds: productForm.has_msds,
        has_liquid: productForm.has_liquid,
        commission_rate: Number(productForm.commission_rate) || 0,
        target_profit_margin: Number(productForm.target_profit_margin) || 0,
        promotion_cost_rate: Number(productForm.promotion_cost_rate) || 0,
        withdrawal_fee_rate: Number(productForm.withdrawal_fee_rate) || 0,
        payment_processing_fee: Number(productForm.payment_processing_fee) || 0,
        return_rate: Number(productForm.return_rate) || 0,
        vat_rate: Number(productForm.vat_rate) || 0,
      }
      if (editingProduct) {
        await productsAPI.update(editingProduct.id, data)
        toast.success('保存成功')
      } else {
        await productsAPI.create(data)
        toast.success('保存成功')
      }
      setProductDialogOpen(false)
      refreshProducts()
    } catch (error) {
      toast.error(getApiError(error) || '保存失败')
    }
  }

  const handleSavePreciseProduct = async () => {
    if (!preciseForm.name || !preciseForm.unit_price || !preciseForm.weight_g) {
      toast.error('请填写名称、进货单价和重量')
      return
    }
    if (Number(preciseForm.weight_g) <= 0) {
      toast.error('商品重量不能为 0')
      return
    }
    if (preciseForm.is_cylinder === 'regular') {
      if (Number(preciseForm.length_cm) <= 0) {
        toast.error('长度不能为 0')
        return
      }
      if (Number(preciseForm.width_cm) <= 0) {
        toast.error('宽度不能为 0')
        return
      }
      if (Number(preciseForm.height_cm) <= 0) {
        toast.error('高度不能为 0')
        return
      }
    }
    if (preciseForm.is_cylinder === 'cylinder') {
      if (Number(preciseForm.cylinder_diameter) <= 0) {
        toast.error('圆柱直径不能为 0')
        return
      }
      if (Number(preciseForm.cylinder_length) <= 0) {
        toast.error('圆柱长度不能为 0')
        return
      }
    }
    const isDuplicate = products.some(p => p.name === preciseForm.name)
    if (isDuplicate) {
      toast.error('已有同名产品')
      return
    }
    try {
      const isCylinder = preciseForm.is_cylinder === 'cylinder'
      const data = {
        name: preciseForm.name,
        unit_price: Number(preciseForm.unit_price),
        labeling_fee: Number(preciseForm.labeling_fee) || 0,
        shipping_fee: Number(preciseForm.shipping_fee) || 0,
        weight_g: Number(preciseForm.weight_g),
        length_cm: isCylinder ? 0 : (Number(preciseForm.length_cm) || 0),
        width_cm: isCylinder ? 0 : (Number(preciseForm.width_cm) || 0),
        height_cm: isCylinder ? 0 : (Number(preciseForm.height_cm) || 0),
        is_cylinder: isCylinder,
        cylinder_diameter: isCylinder ? (Number(preciseForm.cylinder_diameter) || 0) : 0,
        cylinder_length: isCylinder ? (Number(preciseForm.cylinder_length) || 0) : 0,
        has_battery: preciseForm.has_battery,
        battery_capacity_wh: Number(preciseForm.battery_capacity_wh) || 0,
        battery_capacity_mah: Number(preciseForm.battery_capacity_mah) || 0,
        battery_voltage: Number(preciseForm.battery_voltage) || 0,
        battery_capacity_type: preciseForm.battery_capacity_type || 'wh',
        has_msds: preciseForm.has_msds,
        has_liquid: preciseForm.has_liquid,
        commission_rate: Number(preciseForm.commission_rate) / 100,
        target_profit_margin: Number(preciseForm.target_profit_margin) / 100,
        promotion_cost_rate: Number(preciseForm.promotion_cost_rate) / 100,
        withdrawal_fee_rate: Number(preciseForm.withdrawal_fee_rate) / 100,
        payment_processing_fee: Number(preciseForm.payment_processing_fee) / 100,
        return_rate: Number(preciseForm.return_rate) / 100,
        vat_rate: Number(preciseForm.vat_rate) / 100,
      }
      // 重名已被拦截，走到此处一定是新名称 → 始终新建
      const created = await productsAPI.create(data)
      setPreciseForm(prev => ({ ...prev, product_id: String(created.id) }))
      toast.success('保存成功')
      refreshProducts()
    } catch (error) {
      toast.error(getApiError(error) || '保存失败')
    }
  }

  const handleDeleteProduct = (product) => {
    setPendingDeleteProduct(product)
    setDeleteConfirmOpen(true)
  }

  const confirmDeleteProduct = async () => {
    if (!pendingDeleteProduct) return
    try {
      await productsAPI.delete(pendingDeleteProduct.id)
      toast.success('删除成功')
      refreshProducts()
    } catch (error) {
      toast.error(getApiError(error) || '删除失败')
    } finally {
      setDeleteConfirmOpen(false)
      setPendingDeleteProduct(null)
    }
  }

  const handleFastCalculate = async () => {
    if (!fastForm.unit_price || !fastForm.weight_g) {
      toast.error('请填写进货单价和重量')
      return
    }
    setLoading(true)
    setFastResult(null)
    try {
      const productData = {
        unit_price: Number(fastForm.unit_price),
        weight_g: Number(fastForm.weight_g),
        commission_rate: Number(fastForm.commission_rate) / 100,
        target_profit_margin: Number(fastForm.target_profit_margin) / 100,
        promotion_cost_rate: Number(fastForm.promotion_cost_rate) / 100,
        withdrawal_fee_rate: Number(fastForm.withdrawal_fee_rate) / 100,
        payment_processing_fee: Number(fastForm.payment_processing_fee) / 100,
        return_rate: Number(fastForm.return_rate) / 100,
        vat_rate: Number(fastForm.vat_rate) / 100,
      }
      const response = await pricingAPI.calculate(null, 'fast', productData)
      setFastResult(response)
      toast.dismiss(); toast.success('计算完成')
    } catch (error) {
      toast.error(getApiError(error) || '计算失败')
    } finally {
      setLoading(false)
    }
  }

  const handlePreciseCalculate = async () => {
    const p = preciseForm
    if (!p.name && !p.product_id) {
      toast.error('请填写产品名称或从列表选择产品')
      return
    }
    if (!p.weight_g) {
      toast.error('请填写重量')
      return
    }
    // 重量不能为0
    if (Number(p.weight_g) <= 0) {
      toast.error('商品重量不能为 0')
      return
    }
    // 尺寸校验（常规包装时）
    if (p.is_cylinder === 'regular') {
      if (Number(p.length_cm) <= 0) {
        toast.error('长度不能为 0')
        return
      }
      if (Number(p.width_cm) <= 0) {
        toast.error('宽度不能为 0')
        return
      }
      if (Number(p.height_cm) <= 0) {
        toast.error('高度不能为 0')
        return
      }
    }
    // 圆柱包装尺寸校验
    if (p.is_cylinder === 'cylinder') {
      if (Number(p.cylinder_diameter) <= 0) {
        toast.error('圆柱直径不能为 0')
        return
      }
      if (Number(p.cylinder_length) <= 0) {
        toast.error('圆柱长度不能为 0')
        return
      }
    }
    if (!p.product_id && !p.unit_price) {
      toast.error('请选择产品或填写进货单价')
      return
    }
    setLoading(true)
    setPreciseResult(null)
    try {
      const isCylinder = p.is_cylinder === 'cylinder'
      const productData = {
        name: p.name,
        unit_price: Number(p.unit_price),
        labeling_fee: Number(p.labeling_fee) || 0,
        shipping_fee: Number(p.shipping_fee) || 0,
        weight_g: Number(p.weight_g),
        length_cm: isCylinder ? 0 : (Number(p.length_cm) || 0),
        width_cm: isCylinder ? 0 : (Number(p.width_cm) || 0),
        height_cm: isCylinder ? 0 : (Number(p.height_cm) || 0),
        is_cylinder: isCylinder,
        cylinder_diameter: isCylinder ? (Number(p.cylinder_diameter) || 0) : 0,
        cylinder_length: isCylinder ? (Number(p.cylinder_length) || 0) : 0,
        has_battery: p.has_battery,
        battery_capacity_wh: Number(p.battery_capacity_wh) || 0,
        battery_capacity_mah: Number(p.battery_capacity_mah) || 0,
        battery_voltage: Number(p.battery_voltage) || 0,
        has_msds: p.has_msds,
        has_liquid: p.has_liquid,
        commission_rate: Number(p.commission_rate) / 100,
        target_profit_margin: Number(p.target_profit_margin) / 100,
        promotion_cost_rate: Number(p.promotion_cost_rate) / 100,
        withdrawal_fee_rate: Number(p.withdrawal_fee_rate) / 100,
        payment_processing_fee: Number(p.payment_processing_fee) / 100,
        return_rate: Number(p.return_rate) / 100,
        vat_rate: Number(p.vat_rate) / 100,
      }
      // 始终发送 product_data（表单当前值），product_id 只做验证保留
      const response = await pricingAPI.calculate(
        p.product_id ? Number(p.product_id) : null,
        'detailed',
        productData
      )
      setPreciseResult(response)
      toast.dismiss(); toast.success('计算完成')
    } catch (error) {
      toast.error(getApiError(error) || '计算失败')
    } finally {
      setLoading(false)
    }
  }

  const handleProductSelect = (productId) => {
    if (!productId || productId === '__clear__') {
      setPreciseForm({ ...DEFAULT_PRECISE })
      return
    }
    const product = products.find(p => String(p.id) === productId)
    if (product) {
      const isCylinder = !!product.is_cylinder
      setPreciseForm({
        ...DEFAULT_PRECISE,
        product_id: productId,
        name: product.name || '',
        unit_price: String(product.unit_price || ''),
        labeling_fee: String(product.labeling_fee || '0'),
        shipping_fee: String(product.shipping_fee || '0'),
        weight_g: String(product.weight_g || ''),
        length_cm: String(product.length_cm || ''),
        width_cm: String(product.width_cm || ''),
        height_cm: String(product.height_cm || ''),
        is_cylinder: isCylinder ? 'cylinder' : 'regular',
        cylinder_diameter: String(product.cylinder_diameter || ''),
        cylinder_length: String(product.cylinder_length || ''),
        has_battery: !!product.has_battery,
        battery_capacity_wh: String(product.battery_capacity_wh || ''),
        battery_capacity_mah: String(product.battery_capacity_mah || ''),
        battery_voltage: String(product.battery_voltage || ''),
        battery_capacity_type: product.battery_capacity_type || 'wh',
        has_msds: !!product.has_msds,
        has_liquid: !!product.has_liquid,
        commission_rate: String(product.commission_rate ?? '0'),
        target_profit_margin: String(product.target_profit_margin ?? '0'),
        promotion_cost_rate: String(product.promotion_cost_rate ?? '0'),
        withdrawal_fee_rate: String(product.withdrawal_fee_rate ?? '0'),
        payment_processing_fee: String(product.payment_processing_fee ?? '0'),
        return_rate: String(product.return_rate ?? '0'),
        vat_rate: String(product.vat_rate ?? '0'),
      })
    }
  }

  const renderResult = () => {
    const result = activeTab === 'fast' ? fastResult : preciseResult
    if (!result) return null
    const pp = result.price_priority
    const sp = result.speed_priority
    return (
      <div className="mt-6 space-y-6">
        <div className="text-sm text-muted-foreground">
          汇率：1 RUB = {result.exchange_rates?.rub_cny} CNY | 1 USD = {result.exchange_rates?.usd_cny} CNY
        </div>

        {/* 价格优先方案 */}
        <div className="bg-[rgba(59,130,246,0.05)] p-4 rounded">
          <h3 className="text-lg font-semibold mb-3">价格优先方案</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <ResultCard title="自提·陆运" item={pp?.land_pickup} />
              <ResultCard title="自提·空运" item={pp?.air_pickup} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <ResultCard title="送货上门·陆运" item={pp?.land_home} />
              <ResultCard title="送货上门·空运" item={pp?.air_home} />
            </div>
          </div>
        </div>

        {/* 速度优先方案 */}
        <div className="bg-[rgba(34,197,94,0.05)] p-4 rounded">
          <h3 className="text-lg font-semibold mb-3">速度优先方案</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <ResultCard title="自提·陆运" item={sp?.land_pickup} />
              <ResultCard title="自提·空运" item={sp?.air_pickup} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <ResultCard title="送货上门·陆运" item={sp?.land_home} />
              <ResultCard title="送货上门·空运" item={sp?.air_home} />
            </div>
          </div>
        </div>

        {/* 被淘汰的物流 */}
        {result.filtered_logistics && (
          <div className="bg-[rgba(100,100,100,0.15)] p-5 rounded-lg">
            <h3 className="text-lg font-semibold mb-4 text-gray-400">被淘汰的物流</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {['land', 'air'].map(type => (
                <div key={type}>
                  <h4 className="text-sm font-medium mb-2 text-gray-500">{type === 'land' ? '🚛 陆运' : '✈️ 空运'}</h4>
                  {(result.filtered_logistics[type] || []).length > 0 ? (
                    <div className="space-y-2">
                      {result.filtered_logistics[type].map((item) => {
                        const isUnselected = item.reason.includes('未被选中');
                        return (
                          <div key={`${type}-${item.name}`} className={`rounded px-3 py-2 text-sm border ${
                            isUnselected
                              ? 'bg-blue-500/10 border-blue-500/20'
                              : 'bg-red-500/10 border-red-500/20'
                          }`}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-medium">{item.name}</span>
                              <span className={`text-xs px-2 py-0.5 rounded-full ${
                                isUnselected
                                  ? 'bg-blue-500/20 text-blue-400'
                                  : 'bg-red-500/20 text-red-400'
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
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">物流定价计算</h1>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4 grid grid-cols-2 w-full">
          <TabsTrigger value="fast">快速模式</TabsTrigger>
          <TabsTrigger value="precise">{preciseLabel}</TabsTrigger>
        </TabsList>

        {/* ===== 快速模式 ===== */}
        <TabsContent value="fast">
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
                  onChange={(v) => setFastForm({ ...fastForm, commission_rate: v })} defaultVal="0" />
                <RateInput label="运营利润率(%)" value={fastForm.target_profit_margin}
                  onChange={(v) => setFastForm({ ...fastForm, target_profit_margin: v })} defaultVal="20" />
                <RateInput label="推广费率(%)" value={fastForm.promotion_cost_rate}
                  onChange={(v) => setFastForm({ ...fastForm, promotion_cost_rate: v })} defaultVal="5" />
                <RateInput label="打款提现费率(%)" value={fastForm.withdrawal_fee_rate}
                  onChange={(v) => setFastForm({ ...fastForm, withdrawal_fee_rate: v })} defaultVal="2" />
                <RateInput label="收单手续费率(%)" value={fastForm.payment_processing_fee}
                  onChange={(v) => setFastForm({ ...fastForm, payment_processing_fee: v })} defaultVal="1" />
                <RateInput label="历史退货率(%)" value={fastForm.return_rate}
                  onChange={(v) => setFastForm({ ...fastForm, return_rate: v })} defaultVal="3" />
                <RateInput label="增值税率(%)" value={fastForm.vat_rate}
                  onChange={(v) => setFastForm({ ...fastForm, vat_rate: v })} defaultVal="0" />
              </div>

              <Button onClick={handleFastCalculate} disabled={loading} className="w-full">
                {loading ? '计算中...' : '开始计算'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== 精准模式 ===== */}
        <TabsContent value="precise">
          <Card>
            <CardHeader>
              <CardTitle>物流定价（精准模式）</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">

              {/* 产品基本信息 */}
              <div className="space-y-3">
                <Label className="text-sm font-medium">产品基本信息</Label>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">选择产品</Label>
                    <Select value={preciseForm.product_id} onValueChange={handleProductSelect}>
                      <SelectTrigger className="h-8">
                        <SelectValue placeholder="从列表选择..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__clear__">清除选择</SelectItem>
                        {products.map(p => (
                          <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-end gap-2">
                    <Button size="sm" onClick={() => setProductListDialogOpen(true)} className="h-8">打开产品列表</Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">产品名称 <span className="text-red-400">*</span></Label>
                    <Input value={preciseForm.name}
                      onChange={(e) => setPreciseForm({ ...preciseForm, name: e.target.value })}
                      placeholder="必填" className="h-8" />
                  </div>
                  <RateInput label="进货单价（元）" value={preciseForm.unit_price}
                    onChange={(v) => setPreciseForm({ ...preciseForm, unit_price: v })} />
                </div>
              </div>

              {/* 物流规格 */}
              <div className="space-y-3">
                <Label className="text-sm font-medium">物流规格</Label>
                <div className="grid grid-cols-2 gap-3">
                  <RateInput label="商品重量（克）" value={preciseForm.weight_g}
                    onChange={(v) => setPreciseForm({ ...preciseForm, weight_g: v })} />
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
                      onChange={(v) => setPreciseForm({ ...preciseForm, length_cm: v })} />
                    <RateInput label="宽度（厘米）" value={preciseForm.width_cm}
                      onChange={(v) => setPreciseForm({ ...preciseForm, width_cm: v })} />
                    <RateInput label="高度（厘米）" value={preciseForm.height_cm}
                      onChange={(v) => setPreciseForm({ ...preciseForm, height_cm: v })} />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <RateInput label="圆柱直径（厘米）" value={preciseForm.cylinder_diameter}
                      onChange={(v) => setPreciseForm({ ...preciseForm, cylinder_diameter: v })} />
                    <RateInput label="圆柱长度（厘米）" value={preciseForm.cylinder_length}
                      onChange={(v) => setPreciseForm({ ...preciseForm, cylinder_length: v })} />
                  </div>
                )}
              </div>

              {/* 电池和液体 */}
              <div className="space-y-3">
                <Label className="text-sm font-medium">电池和液体</Label>
                <div className="flex gap-4 flex-wrap">
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox checked={preciseForm.has_battery}
                      onCheckedChange={(v) => setPreciseForm({ ...preciseForm, has_battery: !!v })} />
                    含电池
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox checked={preciseForm.has_liquid}
                      onCheckedChange={(v) => setPreciseForm({ ...preciseForm, has_liquid: !!v })} />
                    含液体
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox checked={preciseForm.has_msds}
                      onCheckedChange={(v) => setPreciseForm({ ...preciseForm, has_msds: !!v })} />
                    有 MSDS 证书
                  </label>
                </div>
                {preciseForm.has_battery && (
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">电池容量填写方式</Label>
                    <RadioGroup
                      value={preciseForm.battery_capacity_type}
                      onValueChange={(v) => setPreciseForm({ ...preciseForm, battery_capacity_type: v })}
                      className="flex gap-4"
                    >
                      <div className="flex items-center gap-1.5">
                        <RadioGroupItem value="wh" id="bat-wh" />
                        <Label htmlFor="bat-wh" className="text-sm cursor-pointer">填写 Wh（瓦时）</Label>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <RadioGroupItem value="mah_v" id="bat-mahv" />
                        <Label htmlFor="bat-mahv" className="text-sm cursor-pointer">填写 mAh + V</Label>
                      </div>
                    </RadioGroup>
                    {preciseForm.battery_capacity_type === 'wh' ? (
                      <RateInput label="电池容量（Wh）" value={preciseForm.battery_capacity_wh}
                        onChange={(v) => setPreciseForm({ ...preciseForm, battery_capacity_wh: v })} />
                    ) : (
                      <div className="grid grid-cols-2 gap-3">
                        <RateInput label="电池容量（mAh）" value={preciseForm.battery_capacity_mah}
                          onChange={(v) => setPreciseForm({ ...preciseForm, battery_capacity_mah: v })} />
                        <RateInput label="电池电压（V）" value={preciseForm.battery_voltage}
                          onChange={(v) => setPreciseForm({ ...preciseForm, battery_voltage: v })} />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 定价参数 */}
              <div className="space-y-3">
                <Label className="text-sm font-medium">定价参数</Label>
                <div className="grid grid-cols-2 gap-3">
                  <RateInput label="贴标费用（元）" value={preciseForm.labeling_fee}
                    onChange={(v) => setPreciseForm({ ...preciseForm, labeling_fee: v })} />
                  <RateInput label="供货方不包邮运费（元）" value={preciseForm.shipping_fee}
                    onChange={(v) => setPreciseForm({ ...preciseForm, shipping_fee: v })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <RateInput label="佣金费率(%)" value={preciseForm.commission_rate}
                    onChange={(v) => setPreciseForm({ ...preciseForm, commission_rate: v })} defaultVal="0" />
                  <RateInput label="运营利润率(%)" value={preciseForm.target_profit_margin}
                    onChange={(v) => setPreciseForm({ ...preciseForm, target_profit_margin: v })} defaultVal="20" />
                  <RateInput label="推广费率(%)" value={preciseForm.promotion_cost_rate}
                    onChange={(v) => setPreciseForm({ ...preciseForm, promotion_cost_rate: v })} defaultVal="5" />
                  <RateInput label="打款提现费率(%)" value={preciseForm.withdrawal_fee_rate}
                    onChange={(v) => setPreciseForm({ ...preciseForm, withdrawal_fee_rate: v })} defaultVal="2" />
                  <RateInput label="收单手续费率(%)" value={preciseForm.payment_processing_fee}
                    onChange={(v) => setPreciseForm({ ...preciseForm, payment_processing_fee: v })} defaultVal="1" />
                  <RateInput label="历史退货率(%)" value={preciseForm.return_rate}
                    onChange={(v) => setPreciseForm({ ...preciseForm, return_rate: v })} defaultVal="3" />
                  <RateInput label="增值税率(%)" value={preciseForm.vat_rate}
                    onChange={(v) => setPreciseForm({ ...preciseForm, vat_rate: v })} defaultVal="0" />
                </div>
              </div>

              <div className="flex gap-3">
                <Button onClick={handleSavePreciseProduct} className="flex-1">保存产品</Button>
                <Button onClick={handlePreciseCalculate} disabled={loading} className="flex-1">
                  {loading ? '计算中...' : '开始计算'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {renderResult()}

      {/* 产品列表弹窗 */}
      <Dialog open={productListDialogOpen} onOpenChange={setProductListDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>产品列表</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {products.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">暂无产品，请先创建</p>
            ) : (
              products.map(product => (
                <div key={product.id} className="flex items-center justify-between p-3 border rounded bg-card">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{product.name}</div>
                    <div className="text-xs text-muted-foreground">
                      ¥{product.unit_price} / {product.weight_g}g
                      {product.is_cylinder ? ' / 圆柱' : ' / 常规'}
                    </div>
                  </div>
                  <div className="flex gap-1 ml-2">
                    <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => {
                      setProductListDialogOpen(false)
                      handleEditProduct(product)
                    }}>✏️</Button>
                    <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => handleDeleteProduct(product)}>🗑️</Button>
                  </div>
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProductListDialogOpen(false)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除产品「{pendingDeleteProduct?.name}」吗？此操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => { setDeleteConfirmOpen(false); setPendingDeleteProduct(null) }}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteProduct} className="bg-red-600 hover:bg-red-700">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 新建/编辑产品对话框 */}
      <Dialog open={productDialogOpen} onOpenChange={setProductDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingProduct ? '编辑产品' : '新建产品'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            <div>
              <Label>产品名称 <span className="text-red-400">*</span></Label>
              <Input value={productForm.name}
                onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>进货单价（元） <span className="text-red-400">*</span></Label>
                <Input type="number" value={productForm.unit_price}
                  onChange={(e) => setProductForm({ ...productForm, unit_price: e.target.value })} />
              </div>
              <div>
                <Label>重量（克） <span className="text-red-400">*</span></Label>
                <Input type="number" value={productForm.weight_g}
                  onChange={(e) => setProductForm({ ...productForm, weight_g: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1">
              <Label>包装类型</Label>
              <RadioGroup
                value={productForm.is_cylinder}
                onValueChange={(v) => setProductForm({ ...productForm, is_cylinder: v })}
                className="flex gap-4"
              >
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem value="regular" id="form-pkg-regular" />
                  <Label htmlFor="form-pkg-regular" className="text-sm cursor-pointer">常规包装</Label>
                </div>
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem value="cylinder" id="form-pkg-cylinder" />
                  <Label htmlFor="form-pkg-cylinder" className="text-sm cursor-pointer">圆柱包装</Label>
                </div>
              </RadioGroup>
            </div>
            {productForm.is_cylinder === 'regular' ? (
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>长（厘米）</Label>
                  <Input type="number" value={productForm.length_cm}
                    onChange={(e) => setProductForm({ ...productForm, length_cm: e.target.value })} />
                </div>
                <div>
                  <Label>宽（厘米）</Label>
                  <Input type="number" value={productForm.width_cm}
                    onChange={(e) => setProductForm({ ...productForm, width_cm: e.target.value })} />
                </div>
                <div>
                  <Label>高（厘米）</Label>
                  <Input type="number" value={productForm.height_cm}
                    onChange={(e) => setProductForm({ ...productForm, height_cm: e.target.value })} />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>圆柱直径（厘米）</Label>
                  <Input type="number" value={productForm.cylinder_diameter}
                    onChange={(e) => setProductForm({ ...productForm, cylinder_diameter: e.target.value })} />
                </div>
                <div>
                  <Label>圆柱长度（厘米）</Label>
                  <Input type="number" value={productForm.cylinder_length}
                    onChange={(e) => setProductForm({ ...productForm, cylinder_length: e.target.value })} />
                </div>
              </div>
            )}
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={productForm.has_battery}
                  onCheckedChange={(v) => setProductForm({ ...productForm, has_battery: !!v })} />
                含电池
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={productForm.has_liquid}
                  onCheckedChange={(v) => setProductForm({ ...productForm, has_liquid: !!v })} />
                含液体
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={productForm.has_msds}
                  onCheckedChange={(v) => setProductForm({ ...productForm, has_msds: !!v })} />
                有 MSDS 证书
              </label>
            </div>
            {productForm.has_battery && (
              <div className="space-y-2">
                <Label>电池容量填写方式</Label>
                <RadioGroup
                  value={productForm.battery_capacity_type}
                  onValueChange={(v) => setProductForm({ ...productForm, battery_capacity_type: v })}
                  className="flex gap-4"
                >
                  <div className="flex items-center gap-1.5">
                    <RadioGroupItem value="wh" id="form-bat-wh" />
                    <Label htmlFor="form-bat-wh" className="text-sm cursor-pointer">填写 Wh（瓦时）</Label>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <RadioGroupItem value="mah_v" id="form-bat-mahv" />
                    <Label htmlFor="form-bat-mahv" className="text-sm cursor-pointer">填写 mAh + V</Label>
                  </div>
                </RadioGroup>
                {productForm.battery_capacity_type === 'wh' ? (
                  <div>
                    <Label>电池容量（Wh）</Label>
                    <Input type="number" value={productForm.battery_capacity_wh}
                      onChange={(e) => setProductForm({ ...productForm, battery_capacity_wh: e.target.value })} />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>电池容量（mAh）</Label>
                      <Input type="number" value={productForm.battery_capacity_mah}
                        onChange={(e) => setProductForm({ ...productForm, battery_capacity_mah: e.target.value })} />
                    </div>
                    <div>
                      <Label>电池电压（V）</Label>
                      <Input type="number" value={productForm.battery_voltage}
                        onChange={(e) => setProductForm({ ...productForm, battery_voltage: e.target.value })} />
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>贴标费用（元）</Label>
                <Input type="number" value={productForm.labeling_fee}
                  onChange={(e) => setProductForm({ ...productForm, labeling_fee: e.target.value })} />
              </div>
              <div>
                <Label>供货方不包邮运费（元）</Label>
                <Input type="number" value={productForm.shipping_fee}
                  onChange={(e) => setProductForm({ ...productForm, shipping_fee: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <RateInput label="佣金费率(%)" value={productForm.commission_rate}
                onChange={(v) => setProductForm({ ...productForm, commission_rate: v })} defaultVal="0" />
              <RateInput label="运营利润率(%)" value={productForm.target_profit_margin}
                onChange={(v) => setProductForm({ ...productForm, target_profit_margin: v })} defaultVal="0" />
              <RateInput label="推广费率(%)" value={productForm.promotion_cost_rate}
                onChange={(v) => setProductForm({ ...productForm, promotion_cost_rate: v })} defaultVal="0" />
              <RateInput label="打款提现费率(%)" value={productForm.withdrawal_fee_rate}
                onChange={(v) => setProductForm({ ...productForm, withdrawal_fee_rate: v })} defaultVal="0" />
              <RateInput label="收单手续费率(%)" value={productForm.payment_processing_fee}
                onChange={(v) => setProductForm({ ...productForm, payment_processing_fee: v })} defaultVal="0" />
              <RateInput label="历史退货率(%)" value={productForm.return_rate}
                onChange={(v) => setProductForm({ ...productForm, return_rate: v })} defaultVal="0" />
              <RateInput label="增值税率(%)" value={productForm.vat_rate}
                onChange={(v) => setProductForm({ ...productForm, vat_rate: v })} defaultVal="0" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProductDialogOpen(false)}>取消</Button>
            <Button onClick={handleSaveProduct}>{editingProduct ? '保存修改' : '创建'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
