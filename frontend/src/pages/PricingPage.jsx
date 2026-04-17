import React, { useCallback, useEffect, useState, Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Switch } from '../components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { Checkbox } from '../components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog'
import { Badge } from '../components/ui/badge'
import { toast } from 'sonner'
import { pricingAPI, productsAPI, commissionCategoriesAPI, logisticsAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { Settings2, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../components/ui/collapsible'
import { Link } from 'react-router-dom'
const CostPieChart = React.lazy(() => import('../components/charts/CostPieChart'))

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
  has_liquid: false,
  commission_category_id: '',
  commission_rate: '0',
  target_profit_margin: '0',
  promotion_cost_rate: '0',
  withdrawal_fee_rate: '0',
  payment_processing_fee: '0',
  return_rate: '0',
  vat_rate: '0',
}

function RateInput({ label, value, onChange, defaultVal, step }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        type="number"
        step={step}
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

const CIS_COUNTRIES = [
  { key: 'rfbs_KZ', label: '哈萨克斯坦' },
  { key: 'rfbs_BY', label: '白俄罗斯' },
  { key: 'rfbs_KGZ', label: '吉尔吉斯斯坦' },
  { key: 'rfbs_UZ', label: '乌兹别克斯坦' },
  { key: 'rfbs_GE', label: '格鲁吉亚' },
  { key: 'rfbs_AZ', label: '阿塞拜疆' },
]

export default function PricingPage() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('fast')
  const [loading, setLoading] = useState(false)
  const [fastResult, setFastResult] = useState(null)
  const [preciseResult, setPreciseResult] = useState(null)
  const [groupedResult, setGroupedResult] = useState(null)
  const [groupActiveTab, setGroupActiveTab] = useState('rfbs_ru')
  const [cisActiveTab, setCisActiveTab] = useState('rfbs_KZ')
  const [showBreakeven, setShowBreakeven] = useState(false)
  const [fastForm, setFastForm] = useState(DEFAULT_FAST)
  const [preciseForm, setPreciseForm] = useState(DEFAULT_PRECISE)
  const [commissionCategories, setCommissionCategories] = useState([])
  const [products, setProducts] = useState([])
  const [productDialogOpen, setProductDialogOpen] = useState(false)
  const [productListDialogOpen, setProductListDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [pendingDeleteProduct, setPendingDeleteProduct] = useState(null)
  const [hasLogisticsRules, setHasLogisticsRules] = useState(null)
  const [selectedProductIds, setSelectedProductIds] = useState(new Set())
  const [batchDeleteConfirmOpen, setBatchDeleteConfirmOpen] = useState(false)
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
    commission_category_id: '',
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

  const refreshCommissionCategories = useCallback(() => {
    commissionCategoriesAPI.getAll().then(data => setCommissionCategories(Array.isArray(data) ? data : [])).catch(err => { console.error(err) })
  }, [])

  const refreshProducts = useCallback(() => {
    productsAPI.getAll().then(data => setProducts(Array.isArray(data) ? data : [])).catch(err => { console.error(err) })
  }, [])

  useEffect(() => {
    refreshProducts()
    refreshCommissionCategories()
  }, [refreshCommissionCategories, refreshProducts])

  useEffect(() => {
    if (productListDialogOpen) {
      refreshProducts()
    }
  }, [productListDialogOpen, refreshProducts])

  useEffect(() => {
    const checkLogistics = async () => {
      try {
        const rules = await logisticsAPI.getAll()
        const list = Array.isArray(rules) ? rules : (rules?.items || [])
        setHasLogisticsRules(list.length > 0)
      } catch {
        // fail-open: don't show alert on API failure
        setHasLogisticsRules(true)
      }
    }
    checkLogistics()
  }, [])

  const handleEditProduct = (product) => {
    setEditingProduct(product)
    setProductForm({
      name: product.name || '',
      unit_price: product.unit_price != null ? Number(product.unit_price).toFixed(2) : '',
      labeling_fee: Number(product.labeling_fee || 0).toFixed(2),
      shipping_fee: Number(product.shipping_fee || 0).toFixed(2),
      weight_g: String(product.weight_g || ''),
      length_cm: String(product.length_cm || ''),
      width_cm: String(product.width_cm || ''),
      height_cm: String(product.height_cm || ''),
      is_cylinder: product.is_cylinder ? 'cylinder' : 'regular',
      cylinder_diameter: String(product.cylinder_diameter || ''),
      cylinder_length: String(product.cylinder_length || ''),
      has_battery: !!product.has_battery,
      has_liquid: !!product.has_liquid,
      commission_category_id: product.commission_category_id ? String(product.commission_category_id) : '',
      commission_rate: String(Math.round((product.commission_rate || 0) * 100)),
      target_profit_margin: String(Math.round((product.target_profit_margin || 0) * 100)),
      promotion_cost_rate: String(Math.round((product.promotion_cost_rate || 0) * 100)),
      withdrawal_fee_rate: String(Math.round((product.withdrawal_fee_rate || 0) * 100)),
      payment_processing_fee: String(Math.round((product.payment_processing_fee || 0) * 100)),
      return_rate: String(Math.round((product.return_rate || 0) * 100)),
      vat_rate: String(Math.round((product.vat_rate || 0) * 100)),
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
        has_liquid: productForm.has_liquid,
        commission_category_id: productForm.commission_category_id && productForm.commission_category_id !== 'none' ? Number(productForm.commission_category_id) : null,
        commission_rate: (Number(productForm.commission_rate) || 0) / 100,
        target_profit_margin: (Number(productForm.target_profit_margin) || 0) / 100,
        promotion_cost_rate: (Number(productForm.promotion_cost_rate) || 0) / 100,
        withdrawal_fee_rate: (Number(productForm.withdrawal_fee_rate) || 0) / 100,
        payment_processing_fee: (Number(productForm.payment_processing_fee) || 0) / 100,
        return_rate: (Number(productForm.return_rate) || 0) / 100,
        vat_rate: (Number(productForm.vat_rate) || 0) / 100,
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
        has_liquid: preciseForm.has_liquid,
        commission_category_id: preciseForm.commission_category_id && preciseForm.commission_category_id !== 'none' ? Number(preciseForm.commission_category_id) : null,
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

  const allSelected = products.length > 0 && selectedProductIds.size === products.length
  const someSelected = selectedProductIds.size > 0 && selectedProductIds.size < products.length

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedProductIds(new Set())
    } else {
      setSelectedProductIds(new Set(products.map(p => p.id)))
    }
  }

  const handleSelectProduct = (id) => {
    setSelectedProductIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleBatchDelete = async () => {
    const ids = Array.from(selectedProductIds)
    const results = await Promise.allSettled(
      ids.map(id => productsAPI.delete(id))
    )
    const succeeded = results.filter(r => r.status === 'fulfilled').length
    const failed = results.filter(r => r.status === 'rejected').length

    if (failed === 0) {
      toast.success(`成功删除 ${succeeded} 个产品`)
    } else {
      toast.warning(`删除完成：${succeeded} 个成功，${failed} 个失败`)
    }

    setSelectedProductIds(new Set())
    setBatchDeleteConfirmOpen(false)
    refreshProducts()
  }

  const handleFastCalculate = async () => {
    if (!fastForm.unit_price || !fastForm.weight_g) {
      toast.error('请填写进货单价和重量')
      return
    }
    setLoading(true)
    setShowBreakeven(false)
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
    setShowBreakeven(false)
    setPreciseResult(null)
    setGroupedResult(null)
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
        has_liquid: p.has_liquid,
        commission_category_id: p.commission_category_id && p.commission_category_id !== 'none' ? Number(p.commission_category_id) : null,
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
        'precise',
        productData
      )
      
      const groupedResponse = await pricingAPI.calculateGrouped(
        p.product_id ? Number(p.product_id) : null,
        'precise',
        productData
      )
      
      setPreciseResult(response)
      setGroupedResult(groupedResponse)
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
        unit_price: product.unit_price != null ? Number(product.unit_price).toFixed(2) : '',
        labeling_fee: Number(product.labeling_fee || 0).toFixed(2),
        shipping_fee: Number(product.shipping_fee || 0).toFixed(2),
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
        commission_category_id: product.commission_category_id ? String(product.commission_category_id) : '',
        commission_rate: String(Math.round((product.commission_rate ?? 0) * 100)),
        target_profit_margin: String(Math.round((product.target_profit_margin ?? 0) * 100)),
        promotion_cost_rate: String(Math.round((product.promotion_cost_rate ?? 0) * 100)),
        withdrawal_fee_rate: String(Math.round((product.withdrawal_fee_rate ?? 0) * 100)),
        payment_processing_fee: String(Math.round((product.payment_processing_fee ?? 0) * 100)),
        return_rate: String(Math.round((product.return_rate ?? 0) * 100)),
        vat_rate: String(Math.round((product.vat_rate ?? 0) * 100)),
      })
    }
  }

  const renderResult = () => {
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

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold font-headline tracking-tight mb-6">物流定价计算</h1>

      {hasLogisticsRules === false && (
        <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 flex items-center gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-amber-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <title>警告</title>
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <span className="text-amber-200 text-sm font-medium">请先添加物流规则</span>
          <Link to="/logistics" className="ml-auto text-sm text-indigo-400 hover:text-indigo-300 underline">
            前往物流管理
          </Link>
        </div>
      )}

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
        </TabsContent>

        {/* ===== 精准模式 ===== */}
        <TabsContent value="precise">
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
        </TabsContent>
      </Tabs>

      {renderResult()}

      {/* 产品列表弹窗 */}
      <Dialog open={productListDialogOpen} onOpenChange={(open) => { setProductListDialogOpen(open); if (!open) setSelectedProductIds(new Set()); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>产品列表</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {products.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">暂无产品，请先创建</p>
            ) : (
              <>
                <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10 mb-2">
                  <Checkbox
                    checked={allSelected ? true : someSelected ? "indeterminate" : false}
                    onCheckedChange={handleSelectAll}
                  />
                  <span className="text-sm text-zinc-400">全选</span>
                </div>
                {products.map(product => (
                  <div key={product.id} className="flex items-center justify-between p-3 border rounded bg-card">
                    <Checkbox
                      checked={selectedProductIds.has(product.id)}
                      onCheckedChange={() => handleSelectProduct(product.id)}
                      className="mr-3"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">{product.name}</div>
                      <div className="text-xs text-muted-foreground">
                        ¥{Number(product.unit_price).toFixed(2)} / {product.weight_g}g
                        {product.is_cylinder ? ' / 圆柱' : ' / 常规'}
                      </div>
                    </div>
                    <div className="flex gap-1 ml-2">
                      <Button variant="ghost" size="sm" className="h-7 px-2 transition-all duration-200" onClick={() => {
                        setProductListDialogOpen(false)
                        handleEditProduct(product)
                      }}>✏️</Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2 transition-all duration-200" onClick={() => handleDeleteProduct(product)}>🗑️</Button>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
          <DialogFooter>
            {selectedProductIds.size > 0 && (
              <button
                type="button"
                onClick={() => setBatchDeleteConfirmOpen(true)}
                className="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors mr-auto"
              >
                删除选中 ({selectedProductIds.size})
              </button>
            )}
            <Button variant="outline" onClick={() => setProductListDialogOpen(false)} className="transition-all duration-200">关闭</Button>
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
            <AlertDialogAction onClick={confirmDeleteProduct} className="bg-status-error hover:bg-status-error/85">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={batchDeleteConfirmOpen} onOpenChange={setBatchDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认批量删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除选中的 {selectedProductIds.size} 个产品吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleBatchDelete} className="bg-status-error hover:bg-status-error/85">确认删除</AlertDialogAction>
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
              <Label>产品名称 <span className="text-status-error">*</span></Label>
              <Input value={productForm.name}
                onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>进货单价（元） <span className="text-status-error">*</span></Label>
                <Input type="number" step="0.01" value={productForm.unit_price}
                  onChange={(e) => setProductForm({ ...productForm, unit_price: e.target.value })} />
              </div>
              <div>
                <Label>重量（克） <span className="text-status-error">*</span></Label>
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
              <div className="flex items-center gap-2 text-sm">
                <Checkbox checked={productForm.has_battery}
                  aria-label="产品含电池"
                  onCheckedChange={(v) => setProductForm({ ...productForm, has_battery: !!v })} />
                含电池
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Checkbox checked={productForm.has_liquid}
                  aria-label="产品含液体"
                  onCheckedChange={(v) => setProductForm({ ...productForm, has_liquid: !!v })} />
                含液体
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>贴标费用（元）</Label>
                <Input type="number" step="0.01" value={productForm.labeling_fee}
                  onChange={(e) => setProductForm({ ...productForm, labeling_fee: e.target.value })} />
              </div>
              <div>
                <Label>供货方不包邮运费（元）</Label>
                <Input type="number" step="0.01" value={productForm.shipping_fee}
                  onChange={(e) => setProductForm({ ...productForm, shipping_fee: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">佣金类目</Label>
                <Select value={productForm.commission_category_id} onValueChange={(v) => setProductForm({ ...productForm, commission_category_id: v })}>
                  <SelectTrigger className="h-8">
                    <SelectValue placeholder="选择佣金类目" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">不使用类目(0%)</SelectItem>
                    {commissionCategories.map(cat => (
                      <SelectItem key={cat.id} value={String(cat.id)}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <RateInput label="运营利润率(%)" value={productForm.target_profit_margin}
                onChange={(v) => setProductForm({ ...productForm, target_profit_margin: v })} defaultVal="0" step="1" />
              <RateInput label="推广费率(%)" value={productForm.promotion_cost_rate}
                onChange={(v) => setProductForm({ ...productForm, promotion_cost_rate: v })} defaultVal="0" step="1" />
              <RateInput label="打款提现费率(%)" value={productForm.withdrawal_fee_rate}
                onChange={(v) => setProductForm({ ...productForm, withdrawal_fee_rate: v })} defaultVal="0" step="1" />
              <RateInput label="收单手续费率(%)" value={productForm.payment_processing_fee}
                onChange={(v) => setProductForm({ ...productForm, payment_processing_fee: v })} defaultVal="0" step="1" />
              <RateInput label="历史退货率(%)" value={productForm.return_rate}
                onChange={(v) => setProductForm({ ...productForm, return_rate: v })} defaultVal="0" step="1" />
              <RateInput label="增值税率(%)" value={productForm.vat_rate}
                onChange={(v) => setProductForm({ ...productForm, vat_rate: v })} defaultVal="0" step="1" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProductDialogOpen(false)} className="transition-all duration-200">取消</Button>
            <Button onClick={handleSaveProduct} className="transition-all duration-200">{editingProduct ? '保存修改' : '创建'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
