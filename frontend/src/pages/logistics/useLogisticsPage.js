import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { logisticsAPI } from '../../services/api'
import { useLogisticsStore } from '../../stores/logisticsStore'
import { DEFAULT_FORM } from './logisticsConstants'
import {
  buildLogisticsParams,
  buildLogisticsPayload,
  getApiError,
  mapLogisticsRecordToForm,
} from './logisticsUtils'

export function useLogisticsPage() {
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
  const [togglingIds, setTogglingIds] = useState(new Set())

  const fetchLogistics = useCallback(async () => {
    setLoading(true)
    try {
      const response = await logisticsAPI.getAll(buildLogisticsParams({
        pageSize,
        currentPage,
        activeTab,
        filterFulfillment,
        filterDestination,
      }))
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
        const response = await logisticsAPI.getAll(buildLogisticsParams({
          pageSize,
          currentPage,
          activeTab,
          filterFulfillment,
          filterDestination,
        }))
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

  const handleAdd = useCallback(() => {
    setEditingItem(null)
    setForm(DEFAULT_FORM)
    setDialogOpen(true)
  }, [])

  const handleEdit = useCallback((record) => {
    setEditingItem(record)
    setForm(mapLogisticsRecordToForm(record))
    setDialogOpen(true)
  }, [])

  const handleDelete = useCallback(async (id) => {
    try {
      await logisticsAPI.delete(id)
      removeLogistics(id)
      toast.success('删除成功')
      await fetchLogistics()
    } catch (error) {
      toast.error(getApiError(error) || '删除失败')
    }
  }, [fetchLogistics, removeLogistics])

  const toggleSelect = useCallback((id) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleSelectAll = useCallback((items) => {
    setSelectedIds(new Set(items.map((item) => item.id)))
  }, [])

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const handleBatchDelete = useCallback(async () => {
    try {
      await logisticsAPI.batchDelete(Array.from(selectedIds))
      selectedIds.forEach((id) => {
        removeLogistics(id)
      })
      setSelectedIds(new Set())
      setBatchDeleteDialogOpen(false)
      toast.success('批量删除成功')
      await fetchLogistics()
    } catch (error) {
      toast.error(getApiError(error) || '批量删除失败')
    }
  }, [fetchLogistics, removeLogistics, selectedIds])

  const handleToggleActive = useCallback(async (id, checked) => {
    setTogglingIds((current) => new Set(current).add(id))
    try {
      const response = await logisticsAPI.update(id, { is_active: checked })
      updateLogistics(id, response)
    } catch (error) {
      toast.error(getApiError(error) || '切换状态失败')
    } finally {
      setTogglingIds((current) => {
        const next = new Set(current)
        next.delete(id)
        return next
      })
    }
  }, [updateLogistics])

  const handleToggleTransport = useCallback(async (id, type) => {
    try {
      await logisticsAPI.toggleTransport(id)
      removeLogistics(id)
      setTotal((value) => Math.max(0, value - 1))
      toast.success(type === 'land' ? '已转为空运' : '已转为陆运')
    } catch (error) {
      toast.error(getApiError(error) || '切换失败')
    }
  }, [removeLogistics])

  const handleSubmit = useCallback(async () => {
    if (!form.name) {
      toast.error('请填写名称')
      return
    }

    try {
      const values = buildLogisticsPayload(form)
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
  }, [addLogistics, editingItem, fetchLogistics, form, updateLogistics])

  const setFormField = useCallback((field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
  }, [])

  const handleFulfillmentChange = useCallback((value) => {
    setForm((current) => {
      const next = { ...current, fulfillment_type: value }
      if (value === 'rfbs') {
        next.destination = 'RU'
        next.is_smart = 0
      } else if (value === 'fbp') {
        next.destination = 'RU'
        if (!next.fbp_service_level) next.fbp_service_level = 'economy'
      }
      return next
    })
  }, [])

  const handleFulfillmentChangeFilter = useCallback((value) => {
    setFilterFulfillment(value)
    setCurrentPage(1)
  }, [])

  const handleDestinationChangeFilter = useCallback((value) => {
    setFilterDestination(value)
    setCurrentPage(1)
  }, [])

  const handleTabChange = useCallback((value) => {
    setActiveTab(value)
    setCurrentPage(1)
  }, [])

  const handlePageSizeChange = useCallback((value) => {
    setPageSize(Number(value))
    setCurrentPage(1)
  }, [])

  const handlePrevPage = useCallback(() => {
    setCurrentPage((value) => Math.max(1, value - 1))
  }, [])

  const totalPages = useMemo(() => Math.ceil(total / pageSize) || 1, [pageSize, total])

  const handleNextPage = useCallback(() => {
    setCurrentPage((value) => Math.min(totalPages, value + 1))
  }, [totalPages])

  const handleDeleteDialogChange = useCallback((open) => {
    if (!open) setDeleteConfirmId(null)
  }, [])

  const confirmDelete = useCallback(async () => {
    const id = deleteConfirmId
    setDeleteConfirmId(null)
    if (id !== null) {
      await handleDelete(id)
    }
  }, [deleteConfirmId, handleDelete])

  return {
    logistics,
    loading,
    dialogOpen,
    setDialogOpen,
    editingItem,
    form,
    selectedIds,
    batchDeleteDialogOpen,
    setBatchDeleteDialogOpen,
    deleteConfirmId,
    setDeleteConfirmId,
    filterFulfillment,
    filterDestination,
    activeTab,
    currentPage,
    setCurrentPage,
    pageSize,
    total,
    totalPages,
    togglingIds,
    fetchLogistics,
    handleAdd,
    handleEdit,
    handleDelete,
    toggleSelect,
    handleSelectAll,
    handleClearSelection,
    handleBatchDelete,
    handleToggleActive,
    handleToggleTransport,
    handleSubmit,
    setFormField,
    handleFulfillmentChange,
    handleFulfillmentChangeFilter,
    handleDestinationChangeFilter,
    handleTabChange,
    handlePageSizeChange,
    handlePrevPage,
    handleNextPage,
    handleDeleteDialogChange,
    confirmDelete,
  }
}
