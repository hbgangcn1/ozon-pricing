import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { pricingAPI, productsAPI, commissionCategoriesAPI, logisticsAPI, authAPI } from '../../services/api'
import { useAuthStore } from '../../stores/authStore'
import { DEFAULT_FAST, DEFAULT_PRECISE, DEFAULT_PRODUCT_FORM } from './pricingConstants'
import {
  buildFastPayload,
  buildProductPayload,
  getApiError,
  mapProductToEditorForm,
  mapProductToPreciseForm,
  validateEditorProduct,
  validatePreciseCalculation,
  validatePreciseProduct,
} from './pricingUtils'

export function usePricingCalculation(user) {
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
  const [productForm, setProductForm] = useState(DEFAULT_PRODUCT_FORM)
  const refreshCommissionCategories = useCallback(async () => {
    if (!useAuthStore.getState().hasProfessionalAccess()) {
      setCommissionCategories([])
      return
    }
    try {
      const data = await commissionCategoriesAPI.getAll()
      setCommissionCategories(Array.isArray(data) ? data : [])
    } catch (error) {
      if (error?.name !== 'CanceledError') {
        console.warn('加载佣金分类失败:', error?.message || error)
      }
    }
  }, [])

  const refreshProducts = useCallback(async () => {
    try {
      const data = await productsAPI.getAll()
      setProducts(Array.isArray(data) ? data : [])
    } catch (error) {
      if (error?.name !== 'CanceledError') {
        console.warn('加载产品列表失败:', error?.message || error)
      }
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      const canFetchCommission = useAuthStore.getState().hasProfessionalAccess()
      try {
        const [productData, commissionData] = await Promise.all([
          productsAPI.getAll(),
          canFetchCommission ? commissionCategoriesAPI.getAll() : Promise.resolve([]),
        ])

        if (!cancelled) {
          setProducts(Array.isArray(productData) ? productData : [])
          setCommissionCategories(Array.isArray(commissionData) ? commissionData : [])
        }
      } catch {
        // keep silent on initial load failures
      }
    }

    loadData()
    return () => {
      cancelled = true
    }
  }, [refreshCommissionCategories, refreshProducts])

  useEffect(() => {
    if (productListDialogOpen) {
      refreshProducts()
    }
  }, [productListDialogOpen, refreshProducts])

  useEffect(() => {
    let cancelled = false

    const checkLogistics = async () => {
      try {
        const rules = await logisticsAPI.getAll()
        const list = Array.isArray(rules) ? rules : (rules?.items || [])
        if (!cancelled) {
          setHasLogisticsRules(list.length > 0)
        }
      } catch {
        if (!cancelled) {
          setHasLogisticsRules(true)
        }
      }
    }

    checkLogistics()
    return () => {
      cancelled = true
    }
  }, [])

  const refreshUserAfterCalculation = useCallback(async () => {
    if (!['free', 'monthly'].includes(user?.user_type)) return

    try {
      const me = await authAPI.getMe()
      useAuthStore.getState().setUser(me)
    } catch {
      // intentionally ignored: refresh is best-effort after successful calculation
    }
  }, [user?.user_type])

  const handleEditProduct = useCallback((product) => {
    setEditingProduct(product)
    setProductForm(mapProductToEditorForm(product))
    setProductDialogOpen(true)
  }, [])

  const handleSaveProduct = useCallback(async () => {
    const errorMessage = validateEditorProduct(productForm, products, editingProduct)
    if (errorMessage) {
      toast.error(errorMessage)
      return
    }

    try {
      const data = buildProductPayload(productForm)
      if (editingProduct) {
        await productsAPI.update(editingProduct.id, data)
      } else {
        await productsAPI.create(data)
      }
      toast.success('保存成功')
      setProductDialogOpen(false)
      refreshProducts()
    } catch (error) {
      toast.error(getApiError(error) || '保存失败')
    }
  }, [editingProduct, productForm, products, refreshProducts])

  const handleSavePreciseProduct = useCallback(async () => {
    const errorMessage = validatePreciseProduct(preciseForm, products)
    if (errorMessage) {
      toast.error(errorMessage)
      return
    }

    try {
      const created = await productsAPI.create(buildProductPayload(preciseForm))
      setPreciseForm((current) => ({ ...current, product_id: String(created.id) }))
      toast.success('保存成功')
      refreshProducts()
    } catch (error) {
      toast.error(getApiError(error) || '保存失败')
    }
  }, [preciseForm, products, refreshProducts])

  const handleDeleteProduct = useCallback((product) => {
    setPendingDeleteProduct(product)
    setDeleteConfirmOpen(true)
  }, [])

  const confirmDeleteProduct = useCallback(async () => {
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
  }, [pendingDeleteProduct, refreshProducts])

  const allSelected = useMemo(
    () => products.length > 0 && selectedProductIds.size === products.length,
    [products, selectedProductIds],
  )
  const someSelected = useMemo(
    () => selectedProductIds.size > 0 && selectedProductIds.size < products.length,
    [products.length, selectedProductIds],
  )

  const handleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedProductIds(new Set())
      return
    }

    setSelectedProductIds(new Set(products.map((product) => product.id)))
  }, [allSelected, products])

  const handleSelectProduct = useCallback((id) => {
    setSelectedProductIds((current) => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleBatchDelete = useCallback(async () => {
    const ids = Array.from(selectedProductIds)
    const results = await Promise.allSettled(ids.map((id) => productsAPI.delete(id)))
    const succeeded = results.filter((result) => result.status === 'fulfilled').length
    const failed = results.filter((result) => result.status === 'rejected').length

    if (failed === 0) {
      toast.success(`成功删除 ${succeeded} 个产品`)
    } else {
      toast.warning(`删除完成：${succeeded} 个成功，${failed} 个失败`)
    }

    setSelectedProductIds(new Set())
    setBatchDeleteConfirmOpen(false)
    refreshProducts()
  }, [refreshProducts, selectedProductIds])

  const handleFastCalculate = useCallback(async () => {
    if (!fastForm.unit_price || !fastForm.weight_g) {
      toast.error('请填写进货单价和重量')
      return
    }

    setLoading(true)
    setShowBreakeven(false)
    setFastResult(null)
    try {
      const response = await pricingAPI.calculate(null, 'fast', buildFastPayload(fastForm))
      setFastResult(response)
      toast.dismiss()
      toast.success('计算完成')
      await refreshUserAfterCalculation()
    } catch (error) {
      toast.error(getApiError(error) || '计算失败')
    } finally {
      setLoading(false)
    }
  }, [fastForm, refreshUserAfterCalculation])

  const handlePreciseCalculate = useCallback(async () => {
    const errorMessage = validatePreciseCalculation(preciseForm)
    if (errorMessage) {
      toast.error(errorMessage)
      return
    }

    setLoading(true)
    setShowBreakeven(false)
    setPreciseResult(null)
    setGroupedResult(null)
    try {
      const productData = buildProductPayload(preciseForm)
      const productId = preciseForm.product_id ? Number(preciseForm.product_id) : null
      const response = await pricingAPI.calculate(productId, 'precise', productData)
      const groupedResponse = await pricingAPI.calculateGrouped(productId, 'precise', productData)
      setPreciseResult(response)
      setGroupedResult(groupedResponse)
      toast.dismiss()
      toast.success('计算完成')
      await refreshUserAfterCalculation()
    } catch (error) {
      toast.error(getApiError(error) || '计算失败')
    } finally {
      setLoading(false)
    }
  }, [preciseForm, refreshUserAfterCalculation])

  const handleProductSelect = useCallback((productId) => {
    if (!productId || productId === '__clear__') {
      setPreciseForm({ ...DEFAULT_PRECISE })
      return
    }

    const product = products.find((item) => String(item.id) === productId)
    if (product) {
      setPreciseForm(mapProductToPreciseForm(product, productId))
    }
  }, [products])

  const handleProductListDialogChange = useCallback((open) => {
    setProductListDialogOpen(open)
    if (!open) {
      setSelectedProductIds(new Set())
    }
  }, [])

  return {
    activeTab,
    setActiveTab,
    loading,
    fastResult,
    preciseResult,
    groupedResult,
    groupActiveTab,
    setGroupActiveTab,
    cisActiveTab,
    setCisActiveTab,
    showBreakeven,
    setShowBreakeven,
    fastForm,
    setFastForm,
    preciseForm,
    setPreciseForm,
    commissionCategories,
    products,
    productDialogOpen,
    setProductDialogOpen,
    productListDialogOpen,
    setProductListDialogOpen,
    handleProductListDialogChange,
    editingProduct,
    deleteConfirmOpen,
    setDeleteConfirmOpen,
    pendingDeleteProduct,
    hasLogisticsRules,
    selectedProductIds,
    batchDeleteConfirmOpen,
    setBatchDeleteConfirmOpen,
    productForm,
    setProductForm,
    allSelected,
    someSelected,
    handleEditProduct,
    handleSaveProduct,
    handleSavePreciseProduct,
    handleDeleteProduct,
    confirmDeleteProduct,
    handleSelectAll,
    handleSelectProduct,
    handleBatchDelete,
    handleFastCalculate,
    handlePreciseCalculate,
    handleProductSelect,
  }
}
