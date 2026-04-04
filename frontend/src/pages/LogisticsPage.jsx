import React, { useEffect, useState, useRef } from 'react'
import { Card, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group'
import { Checkbox } from '../components/ui/checkbox'
import { Badge } from '../components/ui/badge'
import { Switch } from '../components/ui/switch'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Zap, Droplets, HelpCircle } from 'lucide-react'
import { logisticsAPI } from '../services/api'
import { useLogisticsStore } from '../stores/logisticsStore'

// 安全提取 API 错误信息，避免将对象渲染到 React toast
const getApiError = (error) => {
  try {
    const detail = error?.response?.data?.detail
    if (!detail) return null
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      // Pydantic 422 错误格式: [{type, loc, msg, input}]
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

const DEFAULT_FORM = {
  name: '',
  type: 'land',
  fee_mode: 'base_weight',
  delivery_method: 'pickup',
  base_fee: '',
  continue_fee: '',
  continue_unit: 'kg',
  min_weight: '',
  max_weight: '',
  min_days: '',
  max_days: '',
  max_sum_of_sides: '',
  max_longest_side: '',
  min_longest_side: '',
  longest_side_threshold: '',
  second_longest_side_threshold: '',
  volume_mode: 'none',
  min_cylinder_sum: '',
  max_cylinder_sum: '',
  min_cylinder_length: '',
  max_cylinder_length: '',
  price_limit_currency: 'RUB',
  price_limit: '',
  price_min: '',
  allow_battery: false,
  battery_wh_limit: '',
  allow_liquid: false,
}

function SectionTitle({ children }) {
  return (
    <h3 className="text-sm font-semibold text-zinc-400 border-b border-zinc-800 pb-1 mb-3">
      {children}
    </h3>
  )
}

function FormRow({ children }) {
  return <div className="grid grid-cols-2 gap-3">{children}</div>
}

function TooltipIcon({ content }) {
  const [show, setShow] = useState(false)
  const timeoutRef = useRef(null)

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => setShow(true), 300)
  }

  const handleMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setShow(false)
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (
    <span className="relative inline-flex ml-1">
      <HelpCircle
        className="h-3 w-3 text-zinc-500 cursor-help"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />
      {show && (
        <span className="absolute left-0 top-full mt-1 z-50 w-64 p-2 text-xs bg-zinc-800 text-zinc-200 rounded border border-zinc-700 shadow-lg">
          {content}
        </span>
      )}
    </span>
  )
}

function FormField({ label, tooltip, children }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center">
        <Label className="text-xs text-zinc-400">{label}</Label>
        {tooltip && <TooltipIcon content={tooltip} />}
      </div>
      {children}
    </div>
  )
}

function RadioLabel({ label, value, itemClassName }) {
  return (
    <div className="flex items-center space-x-2">
      <RadioGroupItem value={value} id={`${value}-${label}`} className={itemClassName} />
      <Label htmlFor={`${value}-${label}`} className="text-sm cursor-pointer">
        {label}
      </Label>
    </div>
  )
}

export default function LogisticsPage() {
  const { logistics, setLogistics, addLogistics, updateLogistics, removeLogistics } = useLogisticsStore()
  const [loading, setLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [form, setForm] = useState(DEFAULT_FORM)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)

  useEffect(() => {
    let cancelled = false
    const doFetch = async () => {
      setLoading(true)
      try {
        const response = await logisticsAPI.getAll()
        if (!cancelled) setLogistics(response)
      } catch (error) {
        if (!cancelled) toast.error('获取物流规则列表失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    doFetch()
    return () => { cancelled = true }
  }, [setLogistics])

  const handleAdd = () => {
    setEditingItem(null)
    setForm(DEFAULT_FORM)
    setDialogOpen(true)
  }

  const handleEdit = (record) => {
    setEditingItem(record)
    setForm({
      name: record.name ?? '',
      type: record.type ?? 'land',
      fee_mode: record.fee_mode ?? 'base_weight',
      delivery_method: record.delivery_method ?? 'pickup',
      base_fee: record.base_fee ?? '',
      continue_fee: record.continue_fee ?? '',
      continue_unit: record.continue_unit ?? 'kg',
      min_weight: record.min_weight ?? '',
      max_weight: record.max_weight ?? '',
      min_days: record.min_days ?? '',
      max_days: record.max_days ?? '',
      max_sum_of_sides: record.max_sum_of_sides ?? '',
      max_longest_side: record.max_longest_side ?? '',
      min_longest_side: record.min_longest_side ?? '',
      longest_side_threshold: record.longest_side_threshold ?? '',
      second_longest_side_threshold: record.second_longest_side_threshold ?? '',
      volume_mode: record.volume_mode ?? 'none',
      min_cylinder_sum: record.min_cylinder_sum ?? '',
      max_cylinder_sum: record.max_cylinder_sum ?? '',
      min_cylinder_length: record.min_cylinder_length ?? '',
      max_cylinder_length: record.max_cylinder_length ?? '',
      price_limit_currency: record.price_limit_currency ?? 'RUB',
      price_limit: record.price_limit_rub ?? record.price_limit_usd ?? '',
      price_min: record.price_min ?? '',
      allow_battery: !!record.allow_battery,
      battery_wh_limit: record.battery_wh_limit ?? '',
      allow_liquid: !!record.allow_liquid,
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    try {
      await logisticsAPI.delete(id)
      removeLogistics(id)
      toast.success('删除成功')
    } catch (error) {
      toast.error('删除失败')
    }
  }

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleSelectAll = (items) => {
    setSelectedIds(new Set(items.map(item => item.id)))
  }

  const handleClearSelection = () => {
    setSelectedIds(new Set())
  }

  const handleBatchDelete = async () => {
    try {
      await logisticsAPI.batchDelete(Array.from(selectedIds))
      selectedIds.forEach(id => removeLogistics(id))
      setSelectedIds(new Set())
      setBatchDeleteDialogOpen(false)
      toast.success('批量删除成功')
    } catch (error) {
      toast.error('批量删除失败')
    }
  }

  const handleToggleActive = async (id, checked) => {
    try {
      const response = await logisticsAPI.update(id, { is_active: checked })
      updateLogistics(id, response)
    } catch (error) {
      toast.error('切换状态失败')
    }
  }

  const handleSubmit = async () => {
    if (!form.name) {
      toast.error('请填写名称')
      return
    }
    try {
      // 空字符串字段不发送（让 Pydantic 使用默认值），非空字段转为数字
      // 注意：continue_unit/fee_mode/delivery_method/volume_mode/type 是字符串，不在此列表中
      const numericFields = [
        'base_fee', 'continue_fee', 'min_weight', 'max_weight',
        'min_days', 'max_days', 'max_sum_of_sides', 'max_longest_side',
        'min_longest_side', 'longest_side_threshold', 'second_longest_side_threshold',
        'max_cylinder_sum', 'min_cylinder_sum', 'max_cylinder_length',
        'min_cylinder_length', 'price_limit', 'price_min',
        'first_weight_g', 'volume_coefficient', 'priority_group',
        'battery_capacity_limit_wh'
      ]
      // continue_unit 是字符串（如 "50g", "1kg"），保持原样不转换
      const values = {}
      for (const [key, val] of Object.entries(form)) {
        if (numericFields.includes(key)) {
          values[key] = val !== '' ? Number(val) : undefined
        } else {
          values[key] = val
        }
      }

      if (values.price_limit_currency === 'RUB') {
        values.price_limit_rub = values.price_limit ? Number(values.price_limit) : null
      } else {
        values.price_limit_usd = values.price_limit ? Number(values.price_limit) : null
      }
      delete values.price_limit
      delete values.price_limit_currency

      if (editingItem) {
        const response = await logisticsAPI.update(editingItem.id, values)
        updateLogistics(editingItem.id, response)
        toast.success('更新成功')
      } else {
        const response = await logisticsAPI.create(values)
        addLogistics(response)
        toast.success('创建成功')
      }
      setDialogOpen(false)
    } catch (error) {
      toast.error(getApiError(error) || '操作失败')
    }
  }

  const setFormField = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const landLogistics = logistics.filter(l => l.type === 'land')
  const airLogistics = logistics.filter(l => l.type === 'air')

  const renderLogisticsList = (items) => (
    <div className="space-y-2">
      {items.length === 0 ? (
        <div className="text-center text-zinc-500 py-8">暂无物流规则</div>
      ) : (
        items.map(item => (
          <Card key={item.id} className={`bg-zinc-900 border-zinc-800 ${!item.is_active ? 'opacity-50' : ''}`}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1 grid grid-cols-9 gap-4 items-center">
                  <Checkbox
                    checked={selectedIds.has(item.id)}
                    onCheckedChange={() => toggleSelect(item.id)}
                  />
                  <div className="font-medium">{item.name}</div>
                  <div>
                    <Badge variant="outline" className="text-xs">
                      {item.delivery_method === 'pickup' ? '取货点' : item.delivery_method === 'door' ? '送货上门' : '未知'}
                    </Badge>
                  </div>
                  <div className="text-sm text-zinc-400">
                    {item.min_days || 0}-{item.max_days || 0}天
                  </div>
                  <div className="text-sm">
                    {item.base_fee != null ? `¥${item.base_fee}` : '-'}
                  </div>
                  <div className="text-sm">
                    {item.continue_fee != null ? `¥${item.continue_fee}/${item.continue_unit || 'kg'}` : '-'}
                  </div>
                  <div className="flex items-center gap-1">
                    {item.allow_battery ? (
                      <Zap className="h-4 w-4 text-green-500" />
                    ) : (
                      <Zap className="h-4 w-4 text-zinc-600" />
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    {item.allow_liquid ? (
                      <Droplets className="h-4 w-4 text-blue-500" />
                    ) : (
                      <Droplets className="h-4 w-4 text-zinc-600" />
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Switch
                      checked={!!item.is_active}
                      onCheckedChange={(checked) => handleToggleActive(item.id, checked)}
                    />
                    <Button variant="ghost" size="icon" onClick={() => handleEdit(item)} aria-label="编辑">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => setDeleteConfirmId(item.id)} aria-label="删除" className="text-red-400">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  )

  const renderForm = () => (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editingItem ? '编辑物流规则' : '添加物流规则'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-6">
          <div>
            <SectionTitle>基本信息</SectionTitle>
            <div className="space-y-4">
              <FormField label="名称">
                <Input
                  value={form.name}
                  onChange={e => setFormField('name', e.target.value)}
                  placeholder="请输入名称"
                />
              </FormField>
              <FormField label="物流类型">
                <RadioGroup
                  value={form.type}
                  onValueChange={v => setFormField('type', v)}
                  className="flex gap-4"
                >
                  <RadioLabel label="陆运" value="land" itemClassName="mt-0.5" />
                  <RadioLabel label="空运" value="air" itemClassName="mt-0.5" />
                </RadioGroup>
              </FormField>
              <FormRow>
                <FormField label="最快时效(天)，未知就填0">
                  <Input
                    type="number"
                    min="0"
                    value={form.min_days}
                    onChange={e => setFormField('min_days', e.target.value)}
                    placeholder="0"
                  />
                </FormField>
                <FormField label="最慢时效(天)，未知就填0">
                  <Input
                    type="number"
                    min="0"
                    value={form.max_days}
                    onChange={e => setFormField('max_days', e.target.value)}
                    placeholder="0"
                  />
                </FormField>
              </FormRow>
            </div>
          </div>

          <div>
            <SectionTitle>计费方式</SectionTitle>
            <div className="space-y-4">
              <FormField label="计费模式">
                <RadioGroup
                  value={form.fee_mode}
                  onValueChange={v => setFormField('fee_mode', v)}
                  className="flex gap-4"
                >
                  <RadioLabel label="基础费用+续重费用" value="base_weight" itemClassName="mt-0.5" />
                  <RadioLabel label="首重费用+续重费用" value="first_weight" itemClassName="mt-0.5" />
                </RadioGroup>
              </FormField>
              <FormRow>
                <FormField label={form.fee_mode === 'first_weight' ? '首重费用' : '基础费用'}>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.base_fee}
                    onChange={e => setFormField('base_fee', e.target.value)}
                    placeholder="0.00"
                  />
                </FormField>
                <FormField label="续重费用">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.continue_fee}
                    onChange={e => setFormField('continue_fee', e.target.value)}
                    placeholder="0.00"
                  />
                </FormField>
              </FormRow>
              <FormRow className="mt-3">
                <FormField label="续重单位">
                  <Select value={form.continue_unit} onValueChange={v => setFormField('continue_unit', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="g">克</SelectItem>
                      <SelectItem value="50g">50克</SelectItem>
                      <SelectItem value="100g">100克</SelectItem>
                      <SelectItem value="500g">500克</SelectItem>
                      <SelectItem value="1kg">1千克</SelectItem>
                    </SelectContent>
                  </Select>
                </FormField>
              </FormRow>
            </div>
          </div>

          <div>
            <SectionTitle>重量限制</SectionTitle>
            <FormRow>
              <FormField
                label="最小重量(g)"
                tooltip="允许运送的最小重量"
              >
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={form.min_weight}
                  onChange={e => setFormField('min_weight', e.target.value)}
                  placeholder="0"
                />
              </FormField>
              <FormField
                label="最大重量(g)"
                tooltip="允许运送的最大重量，0表示无上限"
              >
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={form.max_weight}
                  onChange={e => setFormField('max_weight', e.target.value)}
                  placeholder="无上限"
                />
              </FormField>
            </FormRow>
          </div>

          <div>
            <SectionTitle>体积重量计费方式</SectionTitle>
            <FormField
              label="体积重量计费方式"
              tooltip="当实际重量与体积重量不同时的计费规则"
            >
              <Select value={form.volume_mode} onValueChange={v => setFormField('volume_mode', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">不计算体积重量</SelectItem>
                  <SelectItem value="max">取实际重量与体积重量较大者</SelectItem>
                  <SelectItem value="threshold">最长边超过阈值时按体积重量计费</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
          </div>

          <div>
            <SectionTitle>标准包装</SectionTitle>
            <FormRow className="mt-3">
              <FormField
                label="三边之和上限(cm)"
                tooltip="长+宽+高的总和上限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.max_sum_of_sides}
                  onChange={e => setFormField('max_sum_of_sides', e.target.value)}
                  placeholder="0"
                />
              </FormField>
            </FormRow>
            <FormRow className="mt-3">
              <FormField
                label="最长边上限(cm)"
                tooltip="最大单边长度上限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.max_longest_side}
                  onChange={e => setFormField('max_longest_side', e.target.value)}
                  placeholder="0"
                />
              </FormField>
              <FormField
                label="最长边下限(cm)"
                tooltip="最大单边长度下限，0表示无下限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.min_longest_side}
                  onChange={e => setFormField('min_longest_side', e.target.value)}
                  placeholder="0"
                />
              </FormField>
            </FormRow>
            <FormRow className="mt-3">
              <FormField
                label="第二边长上限(cm)"
                tooltip="第二长边的长度上限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.second_longest_side_threshold}
                  onChange={e => setFormField('second_longest_side_threshold', e.target.value)}
                  placeholder="0"
                />
              </FormField>
              <FormField
                label="第二边长下限(cm)"
                tooltip="第二长边的长度下限，0表示无下限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.second_longest_side_threshold}
                  onChange={e => setFormField('second_longest_side_threshold', e.target.value)}
                  placeholder="0"
                />
              </FormField>
            </FormRow>
          </div>

          <div>
            <SectionTitle>圆柱形包装</SectionTitle>
            <FormRow className="mt-3">
              <FormField
                label="2倍直径与长度之和限制(cm)"
                tooltip="(直径×2)+长度的上限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.max_cylinder_sum}
                  onChange={e => setFormField('max_cylinder_sum', e.target.value)}
                  placeholder="0"
                />
              </FormField>
              <FormField
                label="2倍直径与长度之和下限(cm)"
                tooltip="(直径×2)+长度的下限，0表示无下限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.min_cylinder_sum}
                  onChange={e => setFormField('min_cylinder_sum', e.target.value)}
                  placeholder="0"
                />
              </FormField>
            </FormRow>
            <FormRow className="mt-3">
              <FormField
                label="长度限制(cm)"
                tooltip="圆柱长度的上限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.max_cylinder_length}
                  onChange={e => setFormField('max_cylinder_length', e.target.value)}
                  placeholder="0"
                />
              </FormField>
              <FormField
                label="长度下限(cm)"
                tooltip="圆柱长度的下限，0表示无下限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.min_cylinder_length}
                  onChange={e => setFormField('min_cylinder_length', e.target.value)}
                  placeholder="0"
                />
              </FormField>
            </FormRow>
          </div>

          <div>
            <SectionTitle>送货方式</SectionTitle>
            <RadioGroup
              value={form.delivery_method}
              onValueChange={v => setFormField('delivery_method', v)}
              className="flex gap-4"
            >
              <RadioLabel label="送货到取货点" value="pickup" itemClassName="mt-0.5" />
              <RadioLabel label="送货上门" value="door" itemClassName="mt-0.5" />
              <RadioLabel label="未知" value="unknown" itemClassName="mt-0.5" />
            </RadioGroup>
          </div>

          <div>
            <SectionTitle>价格限制</SectionTitle>
            <FormRow>
              <FormField label="货币单位">
                <Select value={form.price_limit_currency} onValueChange={v => setFormField('price_limit_currency', v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="RUB">RUB (卢布)</SelectItem>
                    <SelectItem value="USD">USD (美元)</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <FormField
                label="价格上限"
                tooltip="订单价格上限"
              >
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price_limit}
                  onChange={e => setFormField('price_limit', e.target.value)}
                  placeholder="0.00"
                />
              </FormField>
            </FormRow>
            <FormRow className="mt-3">
              <FormField
                label="价格下限"
                tooltip="订单价格下限"
              >
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price_min}
                  onChange={e => setFormField('price_min', e.target.value)}
                  placeholder="0.00"
                />
              </FormField>
            </FormRow>
          </div>

          <div>
            <SectionTitle>特殊物品限制</SectionTitle>
            <div className="flex gap-6">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="allow_battery"
                  checked={form.allow_battery}
                  onCheckedChange={v => setFormField('allow_battery', !!v)}
                />
                <Label htmlFor="allow_battery" className="text-sm cursor-pointer">
                  允许电池
                </Label>
              </div>
              {form.allow_battery && (
                <FormField label="电池容量限制(Wh)">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.battery_wh_limit}
                    onChange={e => setFormField('battery_wh_limit', e.target.value)}
                    placeholder="0"
                  />
                </FormField>
              )}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="allow_liquid"
                  checked={form.allow_liquid}
                  onCheckedChange={v => setFormField('allow_liquid', !!v)}
                />
                <Label htmlFor="allow_liquid" className="text-sm cursor-pointer">
                  允许液体
                </Label>
              </div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
          <Button onClick={handleSubmit}>{editingItem ? '更新' : '创建'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">物流规则管理</h1>
        <Button onClick={handleAdd}>
          <Plus className="h-4 w-4 mr-1" />
          添加物流规则
        </Button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8 text-zinc-400">
          <span className="animate-spin mr-2">⏳</span>
          加载中...
        </div>
      )}

      <Tabs defaultValue="land">
        <TabsList className="mb-4">
          <TabsTrigger value="land">陆运</TabsTrigger>
          <TabsTrigger value="air">空运</TabsTrigger>
        </TabsList>
        <TabsContent value="land">
          {renderLogisticsList(landLogistics)}
        </TabsContent>
        <TabsContent value="air">
          {renderLogisticsList(airLogistics)}
        </TabsContent>
      </Tabs>

      {renderForm()}

      <AlertDialog open={deleteConfirmId !== null} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除这条物流规则吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteConfirmId(null)}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => { handleDelete(deleteConfirmId); setDeleteConfirmId(null) }}>确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-zinc-800 border border-zinc-700 rounded-lg px-6 py-3 shadow-lg">
          <span className="text-sm text-zinc-300">已选 {selectedIds.size} 项</span>
          <Button variant="ghost" size="sm" onClick={handleClearSelection}>
            清除
          </Button>
          <Button variant="destructive" size="sm" onClick={() => setBatchDeleteDialogOpen(true)}>
            <Trash2 className="h-4 w-4 mr-1" />
            批量删除
          </Button>
        </div>
      )}

      <AlertDialog open={batchDeleteDialogOpen} onOpenChange={setBatchDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认批量删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除选中的 {selectedIds.size} 项物流规则吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setBatchDeleteDialogOpen(false)}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleBatchDelete}>确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
