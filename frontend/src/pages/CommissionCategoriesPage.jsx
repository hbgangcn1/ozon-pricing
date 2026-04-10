import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Edit2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { commissionCategoriesAPI } from '../services/api'

export default function CommissionCategoriesPage() {
  const [categories, setCategories] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [currentCategory, setCurrentCategory] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    rfbs_tier1_rate: 0,
    rfbs_tier2_rate: 0,
    rfbs_tier3_rate: 0
  })

  const fetchCategories = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await commissionCategoriesAPI.getAll()
      setCategories(data || [])
    } catch (error) {
      if (error?.response?.status !== 404) {
        toast.error('获取佣金类目失败')
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCategories()
  }, [fetchCategories])

  const handleOpenDialog = (category = null) => {
    setCurrentCategory(category)
    if (category) {
      setFormData({
        name: category.name,
        rfbs_tier1_rate: +(category.rfbs_tier1_rate * 100).toFixed(4),
        rfbs_tier2_rate: +(category.rfbs_tier2_rate * 100).toFixed(4),
        rfbs_tier3_rate: +(category.rfbs_tier3_rate * 100).toFixed(4)
      })
    } else {
      setFormData({ name: '', rfbs_tier1_rate: 0, rfbs_tier2_rate: 0, rfbs_tier3_rate: 0 })
    }
    setIsDialogOpen(true)
  }

  const handleDelete = async (id) => {
    if (!window.confirm('确认删除此佣金类目吗？')) return
    try {
      await commissionCategoriesAPI.delete(id)
      toast.success('删除成功')
      fetchCategories()
    } catch (error) {
      toast.error('删除失败')
    }
  }

  const handleSubmit = async () => {
    if (!formData.name) {
      toast.error('类目名称不能为空')
      return
    }
    const payload = {
      name: formData.name,
      rfbs_tier1_rate: (Number(formData.rfbs_tier1_rate) || 0) / 100,
      rfbs_tier2_rate: (Number(formData.rfbs_tier2_rate) || 0) / 100,
      rfbs_tier3_rate: (Number(formData.rfbs_tier3_rate) || 0) / 100
    }
    try {
      if (currentCategory) {
        await commissionCategoriesAPI.update(currentCategory.id, payload)
        toast.success('更新成功')
      } else {
        await commissionCategoriesAPI.create(payload)
        toast.success('创建成功')
      }
      setIsDialogOpen(false)
      fetchCategories()
    } catch (error) {
      toast.error(currentCategory ? '更新失败' : '创建失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">佣金类目管理</h1>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="w-4 h-4 mr-2" />
          新增类目
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>类目名称</TableHead>
                <TableHead>rFBS费率 (≤1500₽)</TableHead>
                <TableHead>rFBS费率 (1500-5000₽)</TableHead>
                <TableHead>rFBS费率 (&gt;5000₽)</TableHead>
                <TableHead>FBP费率 (rFBS-1%)</TableHead>
                <TableHead className="w-[120px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">加载中...</TableCell>
                </TableRow>
              ) : categories.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-text-muted">暂无佣金类目数据</TableCell>
                </TableRow>
              ) : (
                categories.map((cat) => (
                  <TableRow key={cat.id}>
                    <TableCell className="font-medium">{cat.name}</TableCell>
                    <TableCell>{(cat.rfbs_tier1_rate * 100).toFixed(2)}%</TableCell>
                    <TableCell>{(cat.rfbs_tier2_rate * 100).toFixed(2)}%</TableCell>
                    <TableCell>{(cat.rfbs_tier3_rate * 100).toFixed(2)}%</TableCell>
                    <TableCell className="text-text-secondary">
                      {((cat.rfbs_tier1_rate - 0.01) * 100).toFixed(2)}% / {((cat.rfbs_tier2_rate - 0.01) * 100).toFixed(2)}% / {((cat.rfbs_tier3_rate - 0.01) * 100).toFixed(2)}%
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(cat)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(cat.id)} className="text-error hover:text-error-hover">
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{currentCategory ? '编辑佣金类目' : '新增佣金类目'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">类目名称</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="例如: 服装"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tier1">rFBS费率 (≤1500卢布)</Label>
              <Input
                id="tier1"
                type="number"
                step="1"
                value={formData.rfbs_tier1_rate}
                onChange={(e) => setFormData({ ...formData, rfbs_tier1_rate: e.target.value === '' ? '' : parseFloat(e.target.value) || 0 })}
              />
              <span className="text-xs text-text-muted">例如: 12 表示 12%</span>
              <span className="text-xs text-text-secondary">FBP费率: {(Number(formData.rfbs_tier1_rate) - 1).toFixed(2)}%</span>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tier2">rFBS费率 (1500-5000卢布)</Label>
              <Input
                id="tier2"
                type="number"
                step="1"
                value={formData.rfbs_tier2_rate}
                onChange={(e) => setFormData({ ...formData, rfbs_tier2_rate: e.target.value === '' ? '' : parseFloat(e.target.value) || 0 })}
              />
              <span className="text-xs text-text-secondary">FBP费率: {(Number(formData.rfbs_tier2_rate) - 1).toFixed(2)}%</span>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tier3">rFBS费率 (&gt;5000卢布)</Label>
              <Input
                id="tier3"
                type="number"
                step="1"
                value={formData.rfbs_tier3_rate}
                onChange={(e) => setFormData({ ...formData, rfbs_tier3_rate: e.target.value === '' ? '' : parseFloat(e.target.value) || 0 })}
              />
              <span className="text-xs text-text-secondary">FBP费率: {(Number(formData.rfbs_tier3_rate) - 1).toFixed(2)}%</span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>取消</Button>
            <Button onClick={handleSubmit}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
