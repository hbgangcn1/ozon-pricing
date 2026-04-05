import React, { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, Loader2, Package } from 'lucide-react'
import { toast } from 'sonner'
import { productsAPI } from '../services/api'
import { useProductStore } from '../stores/productStore'

import { Button } from '../components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'

function ProductsPage() {
  const { products, setProducts, addProduct, updateProduct, removeProduct } = useProductStore()
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(null)
  
  const [formData, setFormData] = useState({
    name: '',
    category: '',
    unit_price: '',
    weight_g: ''
  })

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const response = await productsAPI.getAll()
      setProducts(response)
    } catch (error) {
      toast.error('获取产品列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    setEditingProduct(null)
    setFormData({ name: '', category: '', unit_price: '', weight_g: '' })
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingProduct(record)
    setFormData({
      name: record.name || '',
      category: record.category || '',
      unit_price: record.unit_price || '',
      weight_g: record.weight_g || ''
    })
    setModalVisible(true)
  }

  const handleDelete = (record) => {
    setPendingDelete(record)
    setDeleteModalVisible(true)
  }

  const confirmDelete = async () => {
    if (!pendingDelete) return
    try {
      await productsAPI.delete(pendingDelete.id)
      removeProduct(pendingDelete.id)
      toast.success('删除成功')
    } catch (error) {
      toast.error('删除失败')
    } finally {
      setDeleteModalVisible(false)
      setPendingDelete(null)
    }
  }

  const handleFormChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async () => {
    if (!formData.name) {
      toast.error('请填写产品名称')
      return
    }

    const payload = {
      name: formData.name,
      category: formData.category,
      unit_price: formData.unit_price ? Number(formData.unit_price) : null,
      weight_g: formData.weight_g ? Number(formData.weight_g) : null
    }

    try {
      if (editingProduct) {
        const response = await productsAPI.update(editingProduct.id, payload)
        updateProduct(editingProduct.id, response)
        toast.success('更新成功')
      } else {
        const response = await productsAPI.create(payload)
        addProduct(response)
        toast.success('创建成功')
      }
      setModalVisible(false)
    } catch (error) {
      toast.error('操作失败')
    }
  }

  const inputClass = "bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 text-text-primary placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out flex w-full"
  const primaryButtonClass = "bg-primary text-white rounded-lg px-4 py-2.5 hover:bg-primary-dim transition-all duration-200 ease-out active:scale-[0.98] font-medium shadow-lg shadow-primary/20 inline-flex items-center justify-center"
  const outlineButtonClass = "bg-surface-high text-text-primary border border-surface-highest rounded-lg px-4 py-2.5 hover:bg-surface-highest hover:border-surface-bright transition-all duration-200 ease-out font-medium inline-flex items-center justify-center"
  const dangerButtonClass = "bg-red-500 text-white rounded-lg px-4 py-2.5 hover:bg-red-600 transition-all duration-200 ease-out active:scale-[0.98] font-medium shadow-lg shadow-red-500/20 inline-flex items-center justify-center"

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-headline font-bold text-2xl text-text-primary tracking-tight">产品管理</h1>
        <button onClick={handleAdd} className={primaryButtonClass}>
          <Plus className="mr-2 h-4 w-4" />
          添加产品
        </button>
      </div>

      <div className="rounded-xl border border-surface-highest bg-surface-container overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-surface-highest hover:bg-surface-high/50 transition-colors">
              <TableHead className="text-text-secondary font-medium w-[80px]">ID</TableHead>
              <TableHead className="text-text-secondary font-medium">产品名称</TableHead>
              <TableHead className="text-text-secondary font-medium">类别</TableHead>
              <TableHead className="text-text-secondary font-medium">单价</TableHead>
              <TableHead className="text-text-secondary font-medium">重量(g)</TableHead>
              <TableHead className="text-text-secondary font-medium w-[150px] text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center">
                  <Loader2 className="h-6 w-6 animate-spin text-primary mx-auto" />
                </TableCell>
              </TableRow>
            ) : products.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-48 text-center text-text-muted">
                  <div className="flex flex-col items-center justify-center space-y-3">
                    <Package className="h-10 w-10 text-surface-highest" />
                    <p className="text-sm">暂无产品数据</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              products.map((record) => (
                <TableRow key={record.id} className="border-b border-surface-highest hover:bg-surface-high/50 transition-colors">
                  <TableCell className="text-text-primary">{record.id}</TableCell>
                  <TableCell className="text-text-primary font-medium">{record.name}</TableCell>
                  <TableCell className="text-text-secondary">{record.category || '-'}</TableCell>
                  <TableCell className="text-text-primary">{record.unit_price != null ? Number(record.unit_price).toFixed(2) : '-'}</TableCell>
                  <TableCell className="text-text-primary">{record.weight_g != null ? Number(record.weight_g).toFixed(2) : '-'}</TableCell>
                  <TableCell className="text-right space-x-2">
                    <button 
                      onClick={() => handleEdit(record)}
                      className="inline-flex items-center text-primary hover:text-primary-dim p-2 rounded-lg hover:bg-surface-high transition-all duration-200"
                    >
                      <Pencil className="h-4 w-4" />
                      <span className="sr-only">编辑</span>
                    </button>
                    <button 
                      onClick={() => handleDelete(record)}
                      className="inline-flex items-center text-red-400 hover:text-red-300 p-2 rounded-lg hover:bg-surface-high transition-all duration-200"
                    >
                      <Trash2 className="h-4 w-4" />
                      <span className="sr-only">删除</span>
                    </button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={modalVisible} onOpenChange={setModalVisible}>
        <DialogContent className="bg-surface-container border border-surface-highest text-text-primary sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="font-headline font-bold text-xl">{editingProduct ? '编辑产品' : '添加产品'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name" className="text-sm font-medium text-text-secondary">产品名称 *</Label>
              <input 
                id="name" 
                name="name" 
                value={formData.name} 
                onChange={handleFormChange} 
                className={inputClass} 
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="category" className="text-sm font-medium text-text-secondary">类别</Label>
              <input 
                id="category" 
                name="category" 
                value={formData.category} 
                onChange={handleFormChange} 
                className={inputClass} 
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="unit_price" className="text-sm font-medium text-text-secondary">单价</Label>
              <input 
                id="unit_price" 
                name="unit_price" 
                type="number"
                step="0.01"
                value={formData.unit_price} 
                onChange={handleFormChange} 
                className={inputClass} 
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="weight_g" className="text-sm font-medium text-text-secondary">重量(g)</Label>
              <input 
                id="weight_g" 
                name="weight_g" 
                type="number"
                step="0.01"
                value={formData.weight_g} 
                onChange={handleFormChange} 
                className={inputClass} 
              />
            </div>
          </div>
          <DialogFooter className="sm:justify-end gap-2 sm:gap-0">
            <button type="button" onClick={() => setModalVisible(false)} className={outlineButtonClass}>
              取消
            </button>
            <button type="button" onClick={handleSubmit} className={primaryButtonClass}>
              确定
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteModalVisible} onOpenChange={(open) => {
        if (!open) {
          setDeleteModalVisible(false)
          setPendingDelete(null)
        }
      }}>
        <DialogContent className="bg-surface-container border border-surface-highest text-text-primary sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle className="font-headline font-bold text-xl text-red-400">确认删除</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            {pendingDelete && (
              <p className="text-text-secondary">确定要删除产品「<strong className="text-text-primary">{pendingDelete.name}</strong>」吗？此操作不可恢复。</p>
            )}
          </div>
          <DialogFooter className="sm:justify-end gap-2 sm:gap-0">
            <button type="button" onClick={() => setDeleteModalVisible(false)} className={outlineButtonClass}>
              取消
            </button>
            <button type="button" onClick={confirmDelete} className={dangerButtonClass}>
              确定删除
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default ProductsPage
