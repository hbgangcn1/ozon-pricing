import React, { useEffect, useState, useRef, useCallback } from 'react'
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Zap, Droplets, HelpCircle, ArrowLeftRight, MoreHorizontal } from 'lucide-react'
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

const CONTINUE_UNIT_MAP = { '1': '1g', '50': '50g', '100': '100g', '500': '500g', '1000': '1kg' }
function normalizeContinueUnit(raw) {
  if (!raw) return '100g'
  const s = String(raw).trim().toLowerCase()
  return CONTINUE_UNIT_MAP[s] || (/^\d+$/.test(s) ? s + 'g' : s)
}

const DEFAULT_FORM = {
  name: '',
  fulfillment_type: 'rfbs',
  destination: 'RU',
  fbp_service_level: '',
  fbp_company: '',
  scoring_group: '',
  is_smart: 0,
  type: 'land',
  fee_mode: 'base_plus_continue',
  delivery_method: 'pickup',
  base_fee: '',
  first_fee: '',
  first_weight_g: '',
  continue_fee: '',
  continue_unit: '100g',
  min_weight: '',
  max_weight: '',
  min_days: '',
  max_days: '',
  max_sum_of_sides: '',
  max_longest_side: '',
  min_length: '',
  longest_side_threshold: '',
  max_second_side: '',
  min_second_side: '',
  max_third_side: '',
  volume_mode: 'none',
  volume_coefficient: '',
  sum_of_sides_threshold: '',
  min_cylinder_sum: '',
  max_cylinder_sum: '',
  min_cylinder_length: '',
  max_cylinder_length: '',
  price_limit_cny: '',
  price_min_cny: '',
  allow_battery: false,
  battery_wh_limit: '',
  allow_liquid: false,
}

function SectionTitle({ children }) {
  return (
    <h3 className="text-sm font-semibold text-text-secondary border-b border-surface-high pb-1 mb-3">
      {children}
    </h3>
  )
}

function FormRow({ children, className = '' }) {
  return <div className={`grid grid-cols-1 sm:grid-cols-2 gap-3 ${className}`}>{children}</div>
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
        className="h-3 w-3 text-text-muted cursor-help"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />
      {show && (
        <span className="absolute left-0 top-full mt-1 z-50 w-64 p-2 text-xs bg-surface-high text-text-primary rounded border border-surface-highest shadow-lg">
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
        <Label className="text-xs text-text-secondary">{label}</Label>
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

  const [filterFulfillment, setFilterFulfillment] = useState('all')
  const [filterDestination, setFilterDestination] = useState('all')
  const [activeTab, setActiveTab] = useState('land')

  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [total, setTotal] = useState(0)

  const fetchLogistics = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        limit: pageSize,
        offset: (currentPage - 1) * pageSize,
        type: activeTab
      }
      if (filterFulfillment !== 'all') params.fulfillment_type = filterFulfillment
      if (filterDestination !== 'all') params.destination = filterDestination
      const response = await logisticsAPI.getAll(params)
      setLogistics(response?.items || [])
      setTotal(response?.total || 0)
    } catch (error) {
      toast.error(getApiError(error) || '获取物流规则列表失败')
    } finally {
      setLoading(false)
    }
  }, [currentPage, pageSize, activeTab, filterFulfillment, filterDestination, setLogistics])

  useEffect(() => {
    const controller = new AbortController()
    ;(async () => {
      setLoading(true)
      try {
        const params = {
          limit: pageSize,
          offset: (currentPage - 1) * pageSize,
          type: activeTab
        }
        if (filterFulfillment !== 'all') params.fulfillment_type = filterFulfillment
        if (filterDestination !== 'all') params.destination = filterDestination
        const response = await logisticsAPI.getAll(params)
        if (controller.signal.aborted) return
        setLogistics(response?.items || [])
        setTotal(response?.total || 0)
      } catch (error) {
        if (controller.signal.aborted) return
        toast.error(getApiError(error) || '获取物流规则列表失败')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    })()
    return () => controller.abort()
  }, [currentPage, pageSize, activeTab, filterFulfillment, filterDestination, setLogistics])

  const handleAdd = () => {
    setEditingItem(null)
    setForm(DEFAULT_FORM)
    setDialogOpen(true)
  }

  const handleEdit = (record) => {
    setEditingItem(record)
    setForm({
      name: record.name ?? '',
      fulfillment_type: record.fulfillment_type ?? 'rfbs',
      destination: record.destination ?? 'RU',
      fbp_service_level: record.fbp_service_level ?? '',
      fbp_company: record.fbp_company ?? '',
      scoring_group: record.scoring_group ?? '',
      is_smart: record.is_smart ?? 0,
      type: record.type ?? 'land',
      fee_mode: record.fee_mode ?? 'base_plus_continue',
      delivery_method: record.delivery_method ?? 'pickup',
      base_fee: record.base_fee != null ? Number(Number(record.base_fee).toFixed(2)) : '',
      first_fee: record.first_fee != null ? Number(Number(record.first_fee).toFixed(2)) : '',
      first_weight_g: record.first_weight_g ?? '',
      continue_fee: record.continue_fee != null ? Number(Number(record.continue_fee).toFixed(5)) : '',
      continue_unit: normalizeContinueUnit(record.continue_unit),
      min_weight: record.min_weight ?? '',
      max_weight: record.max_weight ?? '',
      min_days: record.min_days ?? '',
      max_days: record.max_days ?? '',
      max_sum_of_sides: record.max_sum_of_sides ?? '',
      max_longest_side: record.max_longest_side ?? '',
      min_length: record.min_length ?? '',
      longest_side_threshold: record.longest_side_threshold ?? '',
      max_second_side: record.max_second_side ?? '',
      min_second_side: record.min_second_side ?? '',
      max_third_side: record.max_third_side ?? '',
      volume_mode: record.volume_mode ?? 'none',
      volume_coefficient: record.volume_coefficient ?? '',
      sum_of_sides_threshold: record.sum_of_sides_threshold ?? '',
      min_cylinder_sum: record.min_cylinder_sum ?? '',
      max_cylinder_sum: record.max_cylinder_sum ?? '',
      min_cylinder_length: record.min_cylinder_length ?? '',
      max_cylinder_length: record.max_cylinder_length ?? '',
      price_limit_cny: record.price_limit_cny != null ? Number(record.price_limit_cny).toFixed(2) : '',
      price_min_cny: record.price_min_cny != null ? Number(record.price_min_cny).toFixed(2) : '',
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
      await fetchLogistics()
    } catch (error) {
      toast.error(getApiError(error) || '删除失败')
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
      selectedIds.forEach(id => { removeLogistics(id) })
      setSelectedIds(new Set())
      setBatchDeleteDialogOpen(false)
      toast.success('批量删除成功')
      await fetchLogistics()
    } catch (error) {
      toast.error(getApiError(error) || '批量删除失败')
    }
  }

  const [togglingIds, setTogglingIds] = useState(new Set())

  const handleToggleActive = async (id, checked) => {
    setTogglingIds(prev => new Set(prev).add(id))
    try {
      const response = await logisticsAPI.update(id, { is_active: checked })
      updateLogistics(id, response)
    } catch (error) {
      toast.error(getApiError(error) || '切换状态失败')
    } finally {
      setTogglingIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleSubmit = async () => {
    if (!form.name) {
      toast.error('请填写名称')
      return
    }
    try {
      const numericFields = [
        'base_fee', 'first_fee', 'continue_fee', 'min_weight', 'max_weight',
        'min_days', 'max_days', 'max_sum_of_sides', 'max_longest_side',
        'min_length', 'longest_side_threshold', 'max_second_side', 'min_second_side',
        'max_third_side',
        'max_cylinder_sum', 'min_cylinder_sum', 'max_cylinder_length',
        'min_cylinder_length', 'price_limit_cny', 'price_min_cny',
        'first_weight_g', 'volume_coefficient', 'sum_of_sides_threshold', 'priority_group'
      ]
      const values = {}
      for (const [key, val] of Object.entries(form)) {
        if (numericFields.includes(key)) {
          values[key] = val !== '' ? Number(val) : undefined
        } else {
          values[key] = val
        }
      }

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
      await fetchLogistics()
    } catch (error) {
      toast.error(getApiError(error) || '操作失败')
    }
  }

  const setFormField = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const handleFulfillmentChange = (val) => {
    setForm(prev => {
      const next = { ...prev, fulfillment_type: val }
      if (val === 'rfbs') {
        next.destination = 'RU'
        next.is_smart = 0
      } else if (val === 'fbp') {
        next.destination = 'RU'
        if (!next.fbp_service_level) next.fbp_service_level = 'economy'
      }
      return next
    })
  }

  const handleFulfillmentChangeFilter = (val) => {
    setFilterFulfillment(val)
    setCurrentPage(1)
  }

  const handleDestinationChangeFilter = (val) => {
    setFilterDestination(val)
    setCurrentPage(1)
  }


  const renderLogisticsList = (items) => (
    <div className="space-y-2">
      {items.length === 0 ? (
        <div className="text-center text-text-muted py-8">暂无物流规则</div>
      ) : (
        items.map(item => (
          <Card key={item.id} className={`bg-surface-container border-surface-high transition-all hover:shadow-sm hover:border-surface-highest ${!item.is_active ? 'opacity-60 grayscale-[30%]' : ''}`}>
            <CardContent className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-[auto_2fr_1fr_1fr_1fr_1fr_0.5fr_0.5fr_auto] gap-x-6 gap-y-4 items-center">
                  <div className="flex items-center">
                    <Checkbox
                      checked={selectedIds.has(item.id)}
                      onCheckedChange={() => toggleSelect(item.id)}
                    />
                  </div>
                  <div className="font-medium flex flex-wrap gap-2 items-center min-w-0">
                    <span className="truncate" title={item.name}>{item.name}</span>
                    {item.is_smart === 1 && (
                      <Badge className="bg-status-success/15 text-status-success hover:bg-status-success/25 border-transparent text-[10px] px-1.5 py-0 h-4 transition-colors">Smart</Badge>
                    )}
                  </div>
                  <div>
                    <Badge variant="outline" className="text-xs">
                      {item.delivery_method === 'pickup' ? '取货点' : item.delivery_method === 'door' ? '送货上门' : '未知'}
                    </Badge>
                  </div>
                  <div className="text-sm text-text-secondary">
                    {item.min_days || 0}-{item.max_days || 0}天
                  </div>
                  <div className="text-sm">
                    {item.base_fee != null ? `¥${Number(item.base_fee).toFixed(2)}` : '-'}
                  </div>
                  <div className="text-sm">
                    {item.continue_fee != null ? `¥${Number(item.continue_fee).toFixed(5)}/${normalizeContinueUnit(item.continue_unit)}` : '-'}
                  </div>
                  <div className="flex items-center gap-1">
                    {item.allow_battery ? (
                      <Zap className="h-4 w-4 text-status-success" />
                    ) : (
                      <Zap className="h-4 w-4 text-surface-highest" />
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    {item.allow_liquid ? (
                      <Droplets className="h-4 w-4 text-status-info" />
                    ) : (
                      <Droplets className="h-4 w-4 text-surface-highest" />
                    )}
                  </div>
                  <div className="flex items-center gap-2 justify-end">
                    <Switch
                      checked={!!item.is_active}
                      disabled={togglingIds.has(item.id)}
                      onCheckedChange={(checked) => handleToggleActive(item.id, checked)}
                    />
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="操作菜单">
                          <MoreHorizontal className="h-4 w-4 text-text-secondary" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-36">
                        <DropdownMenuItem onClick={() => handleEdit(item)} className="cursor-pointer" aria-label="编辑">
                          <Pencil className="h-4 w-4 mr-2 text-text-muted" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="cursor-pointer"
                          aria-label={item.type === 'land' ? '转空运' : '转陆运'}
                          onClick={async () => {
                            try {
                              await logisticsAPI.toggleTransport(item.id)
                              removeLogistics(item.id)
                              setTotal(prev => Math.max(0, prev - 1))
                              toast.success(item.type === 'land' ? '已转为空运' : '已转为陆运')
                            } catch (error) {
                              toast.error(getApiError(error) || '切换失败')
                            }
                          }}
                        >
                          <ArrowLeftRight className="h-4 w-4 mr-2 text-text-muted" />
                          {item.type === 'land' ? '转空运' : '转陆运'}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="cursor-pointer text-status-error focus:text-status-error focus:bg-status-error/10"
                          aria-label="删除"
                          onClick={() => setDeleteConfirmId(item.id)}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
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
      <DialogContent className="w-full max-w-4xl max-h-[80vh] overflow-y-auto">
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

              <FormRow>
                <FormField label="发货类型">
                  <Select value={form.fulfillment_type} onValueChange={handleFulfillmentChange}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="rfbs">rFBS</SelectItem>
                      <SelectItem value="fbp">FBP</SelectItem>
                    </SelectContent>
                  </Select>
                </FormField>
                <FormField label="目的国">
                  <Select value={form.destination} onValueChange={v => setFormField('destination', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="RU">俄罗斯(RU)</SelectItem>
                      {(form.fulfillment_type === 'rfbs' || (form.fulfillment_type === 'fbp' && ['economy', 'standard'].includes(form.fbp_service_level))) && (
                        <>
                          <SelectItem value="KZ">哈萨克斯坦(KZ)</SelectItem>
                          <SelectItem value="BY">白俄罗斯(BY)</SelectItem>
                        </>
                      )}
                      {form.fulfillment_type === 'rfbs' && (
                        <>
                          <SelectItem value="KGZ">吉尔吉斯斯坦(KGZ)</SelectItem>
                          <SelectItem value="UZ">乌兹别克斯坦(UZ)</SelectItem>
                          <SelectItem value="GE">格鲁吉亚(GE)</SelectItem>
                          <SelectItem value="AZ">阿塞拜疆(AZ)</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </FormField>
              </FormRow>

              {form.fulfillment_type === 'fbp' && (
                <>
                  <FormRow>
                    <FormField label="FBP 服务等级" tooltip="FBP 仓库服务等级">
                      <Select value={form.fbp_service_level} onValueChange={v => setFormField('fbp_service_level', v)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="economy">Economy</SelectItem>
                          <SelectItem value="standard">Standard</SelectItem>
                          <SelectItem value="express">Express</SelectItem>
                          <SelectItem value="super_express">Super Express</SelectItem>
                        </SelectContent>
                      </Select>
                    </FormField>
                    <FormField label="FBP 公司" tooltip="FBP 仓储服务公司代码">
                      <Select value={form.fbp_company} onValueChange={v => setFormField('fbp_company', v)}>
                        <SelectTrigger><SelectValue placeholder="选择 FBP 公司" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Ural">Ural</SelectItem>
                          <SelectItem value="CEL">CEL</SelectItem>
                          <SelectItem value="GUOO">GUOO</SelectItem>
                          <SelectItem value="RETS">RETS</SelectItem>
                          <SelectItem value="Ural HK">Ural HK</SelectItem>
                          <SelectItem value="ZTO">ZTO</SelectItem>
                          <SelectItem value="XY">XY</SelectItem>
                        </SelectContent>
                      </Select>
                    </FormField>
                  </FormRow>
                  <FormRow>
                    <FormField label="评分组 (Scoring Group)" tooltip="FBP 评分分组，影响定价分组逻辑">
                      <Select value={form.scoring_group} onValueChange={v => setFormField('scoring_group', v)}>
                        <SelectTrigger><SelectValue placeholder="选择评分组" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Extra Small">Extra Small</SelectItem>
                          <SelectItem value="Small">Small</SelectItem>
                          <SelectItem value="Other">Other</SelectItem>
                          <SelectItem value="Budget">Budget</SelectItem>
                          <SelectItem value="Big">Big</SelectItem>
                          <SelectItem value="Premium Small">Premium Small</SelectItem>
                          <SelectItem value="Premium Big">Premium Big</SelectItem>
                        </SelectContent>
                      </Select>
                    </FormField>
                    <FormField label="FBP Smart物流方式" tooltip="启用后该物流将属于Smart物流方式">
                      <div className="flex items-center space-x-3">
                        <Switch
                          checked={form.is_smart === 1}
                          onCheckedChange={v => setFormField('is_smart', v ? 1 : 0)}
                        />
                        <span className="text-sm text-text-secondary">{form.is_smart === 1 ? 'Smart' : '普通'}</span>
                      </div>
                    </FormField>
                  </FormRow>
                </>
              )}

              <FormRow>
                <FormField label="配送方式" tooltip="取货点或送货上门">
                  <Select value={form.delivery_method} onValueChange={v => setFormField('delivery_method', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pickup">取货点</SelectItem>
                      <SelectItem value="door">送货上门</SelectItem>
                    </SelectContent>
                  </Select>
                </FormField>
              </FormRow>

              <FormField label="物流类型">
                <RadioGroup
                  value={form.type}
                  onValueChange={v => setFormField('type', v)}
                  className="flex flex-wrap gap-4"
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
                  className="flex flex-wrap gap-4"
                >
                  <RadioLabel label="基础费用+续重费用" value="base_plus_continue" itemClassName="mt-0.5" />
                  <RadioLabel label="首重费用+续重费用" value="first_weight" itemClassName="mt-0.5" />
                </RadioGroup>
              </FormField>
              <FormRow>
                {form.fee_mode === 'first_weight' ? (
                  <FormField label="首重费用">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.first_fee}
                      onChange={e => setFormField('first_fee', e.target.value)}
                      placeholder="0.00"
                    />
                  </FormField>
                ) : (
                  <FormField label="基础费用">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.base_fee}
                      onChange={e => setFormField('base_fee', e.target.value)}
                      placeholder="0.00"
                    />
                  </FormField>
                )}
                <FormField label="续重费用">
                  <Input
                    type="number"
                    step="0.00001"
                    min="0"
                    value={form.continue_fee}
                    onChange={e => setFormField('continue_fee', e.target.value)}
                    placeholder="0.00000"
                  />
                </FormField>
              </FormRow>
              {form.fee_mode === 'first_weight' && (
                <FormRow className="mt-3">
                  <FormField label="首重重量(克)" tooltip="首重范围内的重量上限，单位为克">
                    <Input
                      type="number"
                      step="1"
                      min="0"
                      value={form.first_weight_g}
                      onChange={e => setFormField('first_weight_g', e.target.value)}
                      placeholder="0"
                    />
                  </FormField>
                </FormRow>
              )}
              <FormRow className="mt-3">
                <FormField label="续重单位">
                  <Select value={form.continue_unit} onValueChange={v => setFormField('continue_unit', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="g">克</SelectItem>
                      <SelectItem value="1g">1克</SelectItem>
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
                  <SelectItem value="max_actual_vs_volume">取实际重量与体积重量较大者</SelectItem>
                  <SelectItem value="longest_side">最长边超过阈值时按体积重量计费</SelectItem>
                  <SelectItem value="sum_of_sides">三边和超过阈值时按体积重量计费</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
            {(form.volume_mode === 'longest_side' || form.volume_mode === 'sum_of_sides' || form.volume_mode === 'max_actual_vs_volume') && (
              <FormRow className="mt-3">
                {(form.volume_mode === 'longest_side') && (
                  <FormField
                    label="最长边阈值(cm)"
                    tooltip="当最长边超过此值时，按体积重量计费"
                  >
                    <Input
                      type="number"
                      min="0"
                      value={form.longest_side_threshold}
                      onChange={e => setFormField('longest_side_threshold', e.target.value)}
                      placeholder="0"
                    />
                  </FormField>
                )}
                {(form.volume_mode === 'sum_of_sides') && (
                  <FormField
                    label="三边和阈值(cm)"
                    tooltip="当长+宽+高超过此值时，按体积重量计费"
                  >
                    <Input
                      type="number"
                      min="0"
                      value={form.sum_of_sides_threshold}
                      onChange={e => setFormField('sum_of_sides_threshold', e.target.value)}
                      placeholder="0"
                    />
                  </FormField>
                )}
                <FormField
                  label="体积重量系数"
                  tooltip="体积重量 = 长×宽×高 / 系数 × 1000 (g)"
                >
                  <Input
                    type="number"
                    min="0"
                    value={form.volume_coefficient}
                    onChange={e => setFormField('volume_coefficient', e.target.value)}
                    placeholder="6000"
                  />
                </FormField>
              </FormRow>
            )}
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
                  value={form.min_length}
                  onChange={e => setFormField('min_length', e.target.value)}
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
                  value={form.max_second_side}
                  onChange={e => setFormField('max_second_side', e.target.value)}
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
                  value={form.min_second_side}
                  onChange={e => setFormField('min_second_side', e.target.value)}
                  placeholder="0"
                />
              </FormField>
            </FormRow>
            <FormRow className="mt-3">
              <FormField
                label="第三边长上限(cm)"
                tooltip="第三长边（最短边）的长度上限，0表示无上限"
              >
                <Input
                  type="number"
                  min="0"
                  value={form.max_third_side}
                  onChange={e => setFormField('max_third_side', e.target.value)}
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
            <SectionTitle>价格限制</SectionTitle>
            <FormRow>
              <FormField
                label="价格上限（元）"
                tooltip="订单价格上限"
              >
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price_limit_cny}
                  onChange={e => setFormField('price_limit_cny', e.target.value)}
                  onBlur={e => {
                    const v = e.target.value
                    if (v !== '') setFormField('price_limit_cny', parseFloat(v).toFixed(2))
                  }}
                  placeholder="0.00"
                />
              </FormField>
              <FormField
                label="价格下限（元）"
                tooltip="订单价格下限"
              >
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price_min_cny}
                  onChange={e => setFormField('price_min_cny', e.target.value)}
                  onBlur={e => {
                    const v = e.target.value
                    if (v !== '') setFormField('price_min_cny', parseFloat(v).toFixed(2))
                  }}
                  placeholder="0.00"
                />
              </FormField>
            </FormRow>
          </div>

          <div>
            <SectionTitle>特殊物品限制</SectionTitle>
            <div className="flex flex-col sm:flex-row flex-wrap gap-4 sm:gap-6">
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
          <Button variant="outline" onClick={() => setDialogOpen(false)} className="transition-all duration-200">取消</Button>
          <Button onClick={handleSubmit} className="transition-all duration-200">{editingItem ? '更新' : '创建'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )

  const totalPages = Math.ceil(total / pageSize) || 1

  const renderPageNumbers = () => {
    const pages = []
    const maxVisible = 7
    
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      pages.push(1)
      if (currentPage > 3) {
        pages.push('...')
      }
      
      let start = Math.max(2, currentPage - 1)
      let end = Math.min(totalPages - 1, currentPage + 1)
      
      if (currentPage <= 3) {
        end = 4
      }
      if (currentPage >= totalPages - 2) {
        start = totalPages - 3
      }
      
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }
      
      if (currentPage < totalPages - 2) {
        pages.push('...')
      }
      pages.push(totalPages)
    }

    return pages.map((page, index) => {
      if (page === '...') {
        const uniqueKey = `ellipsis-${index}-${Math.random()}`
        return <span key={uniqueKey} className="px-2 text-text-muted">...</span>
      }
      return (
        <Button
          key={page}
          variant={currentPage === page ? 'default' : 'ghost'}
          size="sm"
          className={`h-8 w-8 p-0 ${currentPage === page ? '' : 'text-text-secondary hover:text-text-primary'}`}
          onClick={() => setCurrentPage(page)}
        >
          {page}
        </Button>
      )
    })
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-headline tracking-tight">物流规则管理</h1>
        <Button onClick={handleAdd} className="transition-all duration-200">
          <Plus className="h-4 w-4 mr-1" />
          添加物流规则
        </Button>
      </div>

      <div className="flex flex-wrap gap-4 pt-2">
        <div className="flex items-center gap-2">
          <Label className="text-sm font-medium">发货类型:</Label>
          <Select value={filterFulfillment} onValueChange={handleFulfillmentChangeFilter}>
            <SelectTrigger className="w-[140px] h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="rfbs">rFBS</SelectItem>
              <SelectItem value="fbp">FBP</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Label className="text-sm font-medium">目的国:</Label>
          <Select value={filterDestination} onValueChange={handleDestinationChangeFilter}>
            <SelectTrigger className="w-[140px] h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="RU">俄罗斯(RU)</SelectItem>
              <SelectItem value="KZ">哈萨克斯坦(KZ)</SelectItem>
              <SelectItem value="BY">白俄罗斯(BY)</SelectItem>
              <SelectItem value="KGZ">吉尔吉斯斯坦(KGZ)</SelectItem>
              <SelectItem value="UZ">乌兹别克斯坦(UZ)</SelectItem>
              <SelectItem value="GE">格鲁吉亚(GE)</SelectItem>
              <SelectItem value="AZ">阿塞拜疆(AZ)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8 text-text-secondary">
          <span className="animate-spin mr-2">⏳</span>
          加载中...
        </div>
      )}

      <Tabs value={activeTab} onValueChange={(val) => { setActiveTab(val); setCurrentPage(1) }}>
        <TabsList className="mb-4">
          <TabsTrigger value="land">陆运</TabsTrigger>
          <TabsTrigger value="air">空运</TabsTrigger>
        </TabsList>
        <TabsContent value="land">
          {logistics.length > 0 && (
            <div className="flex items-center gap-3 mb-3 px-1">
              <Checkbox
                checked={logistics.length > 0 && logistics.every(item => selectedIds.has(item.id))}
                onCheckedChange={(checked) => {
                  if (checked) {
                    handleSelectAll(logistics)
                  } else {
                    handleClearSelection()
                  }
                }}
                aria-label="全选当前页"
              />
              <span className="text-sm text-text-secondary select-none">全选当前页</span>
            </div>
          )}
          {renderLogisticsList(logistics)}
        </TabsContent>
        <TabsContent value="air">
          {logistics.length > 0 && (
            <div className="flex items-center gap-3 mb-3 px-1">
              <Checkbox
                checked={logistics.length > 0 && logistics.every(item => selectedIds.has(item.id))}
                onCheckedChange={(checked) => {
                  if (checked) {
                    handleSelectAll(logistics)
                  } else {
                    handleClearSelection()
                  }
                }}
                aria-label="全选当前页"
              />
              <span className="text-sm text-text-secondary select-none">全选当前页</span>
            </div>
          )}
          {renderLogisticsList(logistics)}
        </TabsContent>
      </Tabs>

      {renderForm()}

      <div className="flex items-center justify-between border-t border-surface-high pt-4 mt-6">
        <div className="flex items-center text-sm text-text-secondary">
          共 {total} 条
        </div>
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-text-secondary">每页</span>
            <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setCurrentPage(1); }}>
              <SelectTrigger className="h-8 w-[70px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
                <SelectItem value="200">200</SelectItem>
              </SelectContent>
            </Select>
            <span className="text-sm text-text-secondary">条</span>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              className="h-8 px-3"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            >
              上一页
            </Button>
            <div className="flex items-center space-x-1">
              {renderPageNumbers()}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 px-3"
              disabled={currentPage === totalPages || totalPages === 0}
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            >
              下一页
            </Button>
          </div>
        </div>
      </div>

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
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-surface-high border border-surface-highest rounded-lg px-6 py-3 shadow-lg">
          <span className="text-sm text-text-primary">已选 {selectedIds.size} 项</span>
          <Button variant="ghost" size="sm" onClick={handleClearSelection} className="transition-all duration-200">
            清除
          </Button>
          <Button variant="destructive" size="sm" onClick={() => setBatchDeleteDialogOpen(true)} className="transition-all duration-200">
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
