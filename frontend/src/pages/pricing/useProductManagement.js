import { useState, useCallback } from 'react'
import { productsAPI } from '../../services/api'
import { toast } from 'sonner'
import { getApiError } from './pricingUtils'

function useProductManagement() {
  const [products, setProducts] = useState([])
  const [productDialogOpen, setProductDialogOpen] = useState(false)
  const [productListDialogOpen, setProductListDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [pendingDeleteProduct, setPendingDeleteProduct] = useState(null)
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

  const refreshProducts = useCallback(() => {
    productsAPI.getAll().then(data => setProducts(Array.isArray(data) ? data : [])).catch((err) => {
      if (err?.name !== 'CanceledError') console.warn('加载产品列表失败:', err?.message || err)
    })
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

  return {
    products,
    setProducts,
    productDialogOpen,
    setProductDialogOpen,
    productListDialogOpen,
    setProductListDialogOpen,
    editingProduct,
    setEditingProduct,
    deleteConfirmOpen,
    setDeleteConfirmOpen,
    pendingDeleteProduct,
    setPendingDeleteProduct,
    selectedProductIds,
    setSelectedProductIds,
    batchDeleteConfirmOpen,
    setBatchDeleteConfirmOpen,
    productForm,
    setProductForm,
    refreshProducts,
    handleEditProduct,
    handleSaveProduct,
    handleDeleteProduct,
    confirmDeleteProduct,
    allSelected,
    someSelected,
    handleSelectAll,
    handleSelectProduct,
    handleBatchDelete,
  }
}

export default useProductManagement
