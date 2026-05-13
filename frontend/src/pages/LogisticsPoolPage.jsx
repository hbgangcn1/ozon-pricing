import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Plus, Upload, Loader2, Eye, Trash2, Truck, X } from 'lucide-react'
import { toast } from 'sonner'
import { Card, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Checkbox } from '../components/ui/checkbox'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '../components/ui/alert-dialog'
import { VirtualTable } from '../components/ui/virtual-table'
import { logisticsPoolAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { DESTINATION_LABEL_MAP } from './logistics/logisticsConstants'

export default function LogisticsPoolPage() {
  const [logistics, setLogistics] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [addingId, setAddingId] = useState(null)
  const [detailItem, setDetailItem] = useState(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [deleteAllOpen, setDeleteAllOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [isBatchAdding, setIsBatchAdding] = useState(false)
  
  const { isAdmin, hasEnterpriseAccess } = useAuthStore()
  const fileInputRef = useRef(null)
  const canImportExcel = hasEnterpriseAccess()

  const DetailSection = ({ title, fields, cols = 3 }) => {
    const validFields = fields.filter(f => f.value !== null && f.value !== undefined && f.value !== '')
    if (validFields.length === 0) return null

    return (
      <section className="space-y-4 rounded-xl border border-surface-high bg-surface-container p-5 shadow-sm">
        <h3 className="text-base font-semibold text-text-primary flex items-center gap-2">
          <div className="w-1.5 h-5 bg-primary rounded-full" />
          {title}
        </h3>
        <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-${cols}`}>
          {validFields.map((f) => (
            <div key={f.label} className="flex flex-col gap-1 p-3 rounded-lg bg-surface-container border border-surface-high hover:bg-surface-high transition-colors">
              <span className="text-xs text-text-secondary font-medium">{f.label}</span>
              <span className="text-sm font-semibold text-text-primary break-words">
                {f.type === 'boolean' ? (
                  f.value ? (
                    <Badge variant="outline" className="w-fit bg-green-500/10 text-green-600 border-green-500/20 hover:bg-green-500/20">是</Badge>
                  ) : (
                    <Badge variant="outline" className="w-fit bg-surface-high text-text-secondary border-surface-high hover:bg-surface-high/80">否</Badge>
                  )
                ) : (
                  f.value
                )}
              </span>
            </div>
          ))}
        </div>
      </section>
    )
  }

  const fetchLogistics = useCallback(async (signal) => {
    if (!signal?.aborted) setIsLoading(true)
    try {
      const data = await logisticsPoolAPI.getAll({ limit: 1000 }, { signal })
      if (!signal?.aborted) {
        setLogistics(Array.isArray(data) ? data : (data?.items || []))
      }
    } catch (error) {
      if (signal?.aborted) return
      if (error?.name === 'CanceledError' || error?.name === 'AbortError') return
      toast.error('获取物流池数据失败')
    } finally {
      if (!signal?.aborted) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchLogistics(controller.signal)
    return () => controller.abort()
  }, [fetchLogistics])

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    setIsImporting(true)
    try {
      await logisticsPoolAPI.importXlsx(formData)
      toast.success('导入成功')
      fetchLogistics()
    } catch (error) {
      const msg = error?.response?.data?.detail || '导入失败，请检查文件格式'
      toast.error(msg)
    } finally {
      setIsImporting(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleDeleteAll = async () => {
    setIsDeleting(true)
    try {
      const result = await logisticsPoolAPI.deleteAll()
      toast.success(`已删除 ${result.deleted || 0} 条物流数据`)
      fetchLogistics()
      setDeleteAllOpen(false)
    } catch (error) {
      toast.error(error?.response?.data?.detail || '删除失败')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleAddToMyLogistics = useCallback(async (id) => {
    setAddingId(id)
    try {
      await logisticsPoolAPI.addToMyLogistics(id)
      toast.success('已成功添加到我的物流')
    } catch (error) {
      toast.error('添加失败，可能已经存在')
    } finally {
      setAddingId(null)
    }
  }, [])

  const toggleSelect = useCallback((id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleSelectAll = useCallback(() => {
    if (selectedIds.size === logistics.length && logistics.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(logistics.map(item => item.id)))
    }
  }, [logistics, selectedIds])

  const handleClearSelection = () => {
    setSelectedIds(new Set())
  }

  const handleBatchAddToMyLogistics = async () => {
    if (selectedIds.size === 0) return
    setIsBatchAdding(true)
    try {
      const allIds = Array.from(selectedIds)
      const BATCH_SIZE = 200
      let totalAdded = 0
      let totalNotFound = 0
      let totalErrors = 0

      for (let i = 0; i < allIds.length; i += BATCH_SIZE) {
        const batch = allIds.slice(i, i + BATCH_SIZE)
        const result = await logisticsPoolAPI.batchAddToMyLogistics(batch)
        const data = result?.data || result
        totalAdded += data?.added || 0
        totalNotFound += data?.not_found?.length || 0
        totalErrors += data?.errors?.length || 0
      }

      if (totalErrors > 0) {
        toast.error(
          `部分添加失败：成功 ${totalAdded} 条，失败 ${totalErrors} 条${totalNotFound > 0 ? `，${totalNotFound} 条未找到` : ''}`,
          { description: '失败的条目可能是已存在或数据重复的物流规则' }
        )
      } else if (totalNotFound > 0) {
        toast.success(`已添加 ${totalAdded} 条，${totalNotFound} 条未找到`)
      } else {
        toast.success(`已成功添加 ${totalAdded} 条到我的物流`)
      }
      setSelectedIds(new Set())
    } catch (error) {
      toast.error(error?.response?.data?.detail || '批量添加失败')
    } finally {
      setIsBatchAdding(false)
    }
  }

  const columns = useMemo(() => [
    {
      key: 'select',
      header: (
        <Checkbox
          checked={logistics.length > 0 && selectedIds.size === logistics.length}
          onCheckedChange={handleSelectAll}
          aria-label="全选"
        />
      ),
      width: '40px',
      render: (item) => (
        <Checkbox
          checked={selectedIds.has(item.id)}
          onCheckedChange={() => toggleSelect(item.id)}
          aria-label={`选择 ${item.name}`}
        />
      ),
    },
    {
      key: 'name',
      header: '名称',
      width: '1.4fr',
      cellClassName: 'font-medium',
      render: (item) => item.name,
    },
    {
      key: 'fulfillment_type',
      header: '履约类型',
      width: '1fr',
      render: (item) => item.fulfillment_type,
    },
    {
      key: 'destination',
      header: '目的地',
      width: '1fr',
      render: (item) => DESTINATION_LABEL_MAP[item.destination] ?? item.destination,
    },
    {
      key: 'fbp_service_level',
      header: 'FBP服务等级',
      width: '1fr',
      render: (item) => item.fbp_service_level || '-',
    },
    {
      key: 'is_smart',
      header: '标签',
      width: '1fr',
      render: (item) => item.is_smart ? (
        <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20">
          智能分配
        </Badge>
      ) : '-',
    },
    {
      key: 'is_active',
      header: '状态',
      width: '1fr',
      render: (item) => item.is_active ? (
        <Badge variant="default" className="bg-green-500 hover:bg-green-600">生效中</Badge>
      ) : (
        <Badge variant="secondary">已停用</Badge>
      ),
    },
    {
      key: 'actions',
      header: '操作',
      width: '220px',
      render: (item) => (
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => { setDetailItem(item); setDetailOpen(true) }}
          >
            <Eye className="w-3 h-3 mr-1" />
            查看
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => handleAddToMyLogistics(item.id)}
            disabled={addingId === item.id}
          >
            {addingId === item.id ? (
              <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            ) : (
              <Plus className="w-3 h-3 mr-1" />
            )}
            添加到我的
          </Button>
        </div>
      ),
    },
  ], [addingId, handleAddToMyLogistics, handleSelectAll, logistics, selectedIds, toggleSelect])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-text-primary tracking-tight">公共物流池</h1>
          {logistics.length > 0 && (
            <Badge variant="secondary" className="bg-slate-100 text-text-muted hover:bg-slate-200 font-normal px-2.5 py-0.5 text-sm">
              {logistics.length}
            </Badge>
          )}
        </div>
        
        {isAdmin() && (
          <div className="flex gap-2">
            <AlertDialog open={deleteAllOpen} onOpenChange={setDeleteAllOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  <Trash2 className="w-4 h-4 mr-2" />
                  删除全部
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>确认删除所有物流数据？</AlertDialogTitle>
                  <AlertDialogDescription>
                    此操作将删除公共物流池中的所有数据，且不可恢复。确定要继续吗？
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={handleDeleteAll} disabled={isDeleting}>
                    {isDeleting ? '删除中...' : '确认删除'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <div>
              <input
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                ref={fileInputRef}
                onChange={handleFileChange}
              />
              <Button 
                onClick={() => fileInputRef.current?.click()} 
                disabled={isImporting || !canImportExcel}
                title={!canImportExcel ? '此功能需要企业版或更高订阅等级' : undefined}
                variant="outline"
              >
                {isImporting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4 mr-2" />
                )}
                导入 Excel
              </Button>
            </div>
          </div>
        )}
      </div>

      <Card>
        <CardContent className="pt-6">
          <VirtualTable
            items={logistics}
            columns={columns}
            getItemKey={(item) => item.id}
            rowHeight={53}
            maxHeight="calc(100vh - 280px)"
            loading={isLoading}
            loadingContent={<span>加载中...</span>}
            emptyContent={<span className="text-text-muted">暂无物流数据</span>}
            rowClassName={(item) => selectedIds.has(item.id) ? 'bg-primary/5' : ''}
          />
        </CardContent>
      </Card>

      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-surface-high border border-surface-highest rounded-lg px-6 py-3 shadow-lg">
          <span className="text-sm text-text-primary font-medium">已选 {selectedIds.size} 项</span>
          <Button
            size="sm"
            onClick={handleBatchAddToMyLogistics}
            disabled={isBatchAdding}
          >
            {isBatchAdding ? (
              <Loader2 className="w-4 h-4 mr-1 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-1" />
            )}
            全部添加到我的物流
          </Button>
          <Button variant="ghost" size="sm" onClick={handleClearSelection}>
            <X className="w-4 h-4 mr-1" />
            取消
          </Button>
        </div>
      )}

      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-4xl bg-surface-container p-0 border-surface-high shadow-lg">
          <DialogHeader className="px-6 py-5 bg-surface-container border-b border-surface-high flex flex-row items-center gap-4">
            <div className="bg-primary/10 text-primary p-2.5 rounded-lg border border-primary/20">
              <Truck className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <DialogTitle className="text-xl font-bold tracking-tight text-text-primary">
                {detailItem?.name || '物流详情'}
              </DialogTitle>
              <div className="text-sm text-text-secondary font-medium">
  {DESTINATION_LABEL_MAP[detailItem?.destination] ?? detailItem?.destination} · {detailItem?.fulfillment_type || '履约类型未知'}
              </div>
            </div>
          </DialogHeader>

          <div className="max-h-[calc(85vh-90px)] overflow-y-auto px-6 py-5 space-y-6">
            <DetailSection title="基本信息" fields={[
              { label: '类型', value: detailItem?.type === 'land' ? '陆运' : detailItem?.type === 'air' ? '空运' : detailItem?.type },
              { label: '配送方式', value: detailItem?.delivery_method },
              { label: '履约类型', value: detailItem?.fulfillment_type },
      { label: '目的地', value: DESTINATION_LABEL_MAP[detailItem?.destination] ?? detailItem?.destination }
            ]} />

            <DetailSection title="时效" fields={[
              { label: '最短天数', value: detailItem?.min_days ? `${detailItem.min_days} 天` : null },
              { label: '最长天数', value: detailItem?.max_days ? `${detailItem.max_days} 天` : null }
            ]} />

            <DetailSection title="价格限制" cols={2} fields={[
              { label: '人民币上限', value: detailItem?.price_limit_cny != null ? `¥${detailItem.price_limit_cny}` : null },
              { label: '人民币下限', value: detailItem?.price_min_cny != null ? `¥${detailItem.price_min_cny}` : null }
            ]} />

            <DetailSection title="重量限制" fields={[
              { label: '最小重量', value: detailItem?.min_weight ? `${detailItem.min_weight} g` : null },
              { label: '最大重量', value: detailItem?.max_weight ? `${detailItem.max_weight} g` : null }
            ]} />

            <DetailSection title="尺寸限制" fields={[
              { label: '最大三边和', value: detailItem?.max_sum_of_sides ? `${detailItem.max_sum_of_sides} cm` : null },
              { label: '最长边', value: detailItem?.max_longest_side ? `${detailItem.max_longest_side} cm` : null },
              { label: '第二长边', value: detailItem?.max_second_side ? `${detailItem.max_second_side} cm` : null },
              { label: '第三长边', value: detailItem?.max_third_side ? `${detailItem.max_third_side} cm` : null },
              { label: '第二边长下限(cm)', value: detailItem?.min_second_side ? `${detailItem.min_second_side} cm` : null },
              { label: '最长边下限(cm)', value: detailItem?.min_length ? `${detailItem.min_length} cm` : null },
              { label: '最长边阈值', value: detailItem?.longest_side_threshold ? `${detailItem.longest_side_threshold} cm` : null }
            ]} />

            <DetailSection title="圆柱限制" fields={[
              { label: '最大周长和', value: detailItem?.max_cylinder_sum ? `${detailItem.max_cylinder_sum} cm` : null },
              { label: '最小周长和', value: detailItem?.min_cylinder_sum ? `${detailItem.min_cylinder_sum} cm` : null },
              { label: '最大长度', value: detailItem?.max_cylinder_length ? `${detailItem.max_cylinder_length} cm` : null },
              { label: '最小长度', value: detailItem?.min_cylinder_length ? `${detailItem.min_cylinder_length} cm` : null }
            ]} />

            <DetailSection title="体积" fields={[
              { label: '体积模式', value: detailItem?.volume_mode },
              { label: '体积系数', value: detailItem?.volume_coefficient },
              { label: '最长边阈值', value: detailItem?.longest_side_threshold ? `${detailItem.longest_side_threshold} cm` : null },
              { label: '三边和阈值', value: detailItem?.sum_of_sides_threshold ? `${detailItem.sum_of_sides_threshold} cm` : null }
            ]} />

            <DetailSection title="特殊物品" fields={[
              { label: '允许电池', value: detailItem?.allow_battery, type: 'boolean' },
              { label: '允许液体', value: detailItem?.allow_liquid, type: 'boolean' }
            ]} />

            <DetailSection title="费用配置" fields={[
              { label: '费用模式', value: detailItem?.fee_mode },
              { label: '基础费用', value: detailItem?.base_fee },
              { label: '首重费用', value: detailItem?.first_fee },
              { label: '首重(g)', value: detailItem?.first_weight_g },
              { label: '续重费用', value: detailItem?.continue_fee },
              { label: '续重单位', value: detailItem?.continue_unit }
            ]} />

            <DetailSection title="其他" fields={[
              { label: '优先组', value: detailItem?.priority_group },
              { label: '智能分配', value: detailItem?.is_smart, type: 'boolean' },
              { label: 'FBP 服务等级', value: detailItem?.fbp_service_level },
              { label: 'FBP 公司', value: detailItem?.fbp_company },
              { label: '来源文件', value: detailItem?.source_file },
              { label: '是否启用', value: detailItem?.is_active, type: 'boolean' }
            ]} />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
