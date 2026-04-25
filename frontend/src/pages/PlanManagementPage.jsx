import { useState, useEffect, useCallback } from 'react'
import { Edit, Save, X, Plus, List, Trash2, Power } from 'lucide-react'
import { toast } from 'sonner'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Badge } from '../components/ui/badge'
import { Switch } from '../components/ui/switch'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Textarea } from '../components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog'
import { plansAPI } from '../services/api'

const apiPlanToLocal = (p) => ({
  id: p.id,
  code: p.code,
  name: p.name,
  displayPriceMonth: p.display_price_month,
  displayPriceYear: p.display_price_year,
  actualPriceMonth: p.actual_price_month,
  actualPriceYear: p.actual_price_year,
  testPriceMonth: p.test_price_month,
  testPriceYear: p.test_price_year,
  calcLimit: p.calc_limit,
  logisticsTemplate: p.logistics_limit,
  sort: p.sort,
  status: p.status,
  description: p.description || '',
  features: p.features || [],
})

const localPlanToApi = (p) => ({
  plan_code: p.code,
  plan_name: p.name,
  display_price_month: p.displayPriceMonth,
  display_price_year: p.displayPriceYear,
  actual_price_month: p.actualPriceMonth,
  actual_price_year: p.actualPriceYear,
  test_price_month: p.testPriceMonth,
  test_price_year: p.testPriceYear,
  calc_limit: p.calcLimit,
  logistics_limit: p.logisticsTemplate,
  description: p.description,
  features: Array.isArray(p.features) ? p.features : [],
  sort_order: p.sort,
  is_active: p.status ? 1 : 0,
})

function PlanCard({ plan, onEdit, isEditing, onDelete, onToggle }) {
  return (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle>{plan.name}</CardTitle>
            <Badge variant={plan.status ? 'default' : 'secondary'}>
              {plan.status ? '已上架' : '未上架'}
            </Badge>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onToggle(plan.id)}>
              <Power className="w-4 h-4 mr-2" />
              {plan.status ? '下架' : '上架'}
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => onEdit(plan.id)}
              disabled={isEditing}
            >
              <Edit className="w-4 h-4 mr-2" />
              编辑
            </Button>
            <Button variant="outline" size="sm" onClick={() => onDelete(plan.id)} className="text-red-400 hover:text-red-300">
              <Trash2 className="w-4 h-4 mr-2" />
              删除
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>显示价（月）</TableHead>
              <TableHead>显示价（年）</TableHead>
              <TableHead>实际价（月）</TableHead>
              <TableHead>实际价（年）</TableHead>
              <TableHead>测试价（月）</TableHead>
              <TableHead>测试价（年）</TableHead>
              <TableHead>计算次数</TableHead>
              <TableHead>物流模板</TableHead>
              <TableHead>排序</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>¥{Number(plan.displayPriceMonth).toFixed(2)}</TableCell>
              <TableCell>{plan.displayPriceYear ? `¥${Number(plan.displayPriceYear).toFixed(2)}` : '-'}</TableCell>
              <TableCell>¥{Number(plan.actualPriceMonth).toFixed(2)}</TableCell>
              <TableCell>{plan.actualPriceYear ? `¥${Number(plan.actualPriceYear).toFixed(2)}` : '-'}</TableCell>
              <TableCell>¥{Number(plan.testPriceMonth).toFixed(2)}</TableCell>
              <TableCell>{plan.testPriceYear ? `¥${Number(plan.testPriceYear).toFixed(2)}` : '-'}</TableCell>
              <TableCell>{plan.calcLimit === -1 ? '无限' : `${plan.calcLimit}次/天`}</TableCell>
              <TableCell>{plan.logisticsTemplate === -1 ? '无限' : plan.logisticsTemplate}</TableCell>
              <TableCell>{plan.sort}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        
        <div className="mt-4">
          <p className="text-text-secondary text-sm">{plan.description}</p>
        </div>
        
        <div className="mt-4 flex flex-wrap gap-2">
          {plan.features.map((f) => (
            <Badge key={f} variant="secondary">{f}</Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function PlanEditForm({ plan, onSave, onCancel, isNew }) {
  const [formData, setFormData] = useState(() => {
    const data = { ...plan, features: Array.isArray(plan.features) ? plan.features.join('|') : '' }
    for (const f of ['displayPriceMonth', 'displayPriceYear', 'actualPriceMonth', 'actualPriceYear', 'testPriceMonth', 'testPriceYear']) {
      data[f] = Number(data[f] || 0).toFixed(2)
    }
    return data
  })

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const PRICE_FIELDS = new Set([
    'displayPriceMonth', 'displayPriceYear',
    'actualPriceMonth', 'actualPriceYear',
    'testPriceMonth', 'testPriceYear',
  ])

  const handleNumberChange = (field, value) => {
    if (value === '') {
      setFormData(prev => ({ ...prev, [field]: 0 }))
      return
    }
    let numValue = parseFloat(value)
    if (PRICE_FIELDS.has(field)) {
      numValue = Math.round(numValue * 100) / 100
    }
    setFormData(prev => ({ ...prev, [field]: numValue }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const featuresArray = formData.features 
      ? formData.features.split('|').map(f => f.trim()).filter(f => f)
      : []
    const { _prevCalcLimit, _prevLogisticsTemplate, ...submitData } = formData
    onSave(plan.id, { ...submitData, features: featuresArray })
  }

  return (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{isNew ? '新增套餐' : `编辑套餐: ${plan.name}`}</CardTitle>
          <div className="flex gap-2">
            <Button type="button" onClick={handleSubmit}>
              <Save className="w-4 h-4 mr-2" />
              保存
            </Button>
            <Button variant="outline" onClick={onCancel}>
              <X className="w-4 h-4 mr-2" />
              取消
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {isNew && (
              <div className="space-y-2">
                <Label>套餐代码</Label>
                <Input
                  value={formData.code}
                  onChange={(e) => handleChange('code', e.target.value)}
                  placeholder="例如: basic_plan"
                  required
                />
              </div>
            )}
            <div className="space-y-2">
              <Label>套餐名称</Label>
              <Input
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="例如: 基础版"
                required
              />
            </div>
          </div>
          
          {/* 价格配置 */}
          <div>
            <h3 className="text-lg font-medium text-text-primary mb-4 font-headline tracking-tight">💵 价格配置</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <div className="space-y-2">
                <Label>显示价（月）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.displayPriceMonth}
                  onChange={(e) => handleNumberChange('displayPriceMonth', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>显示价（年）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.displayPriceYear}
                  onChange={(e) => handleNumberChange('displayPriceYear', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>实际价（月）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.actualPriceMonth}
                  onChange={(e) => handleNumberChange('actualPriceMonth', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>实际价（年）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.actualPriceYear}
                  onChange={(e) => handleNumberChange('actualPriceYear', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>测试价（月）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.testPriceMonth}
                  onChange={(e) => handleNumberChange('testPriceMonth', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>测试价（年）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.testPriceYear}
                  onChange={(e) => handleNumberChange('testPriceYear', e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* 功能配置 */}
          <div>
            <h3 className="text-lg font-medium text-text-primary mb-4 font-headline tracking-tight">⚙️ 功能配置</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label>计算次数</Label>
                <div className="flex items-center gap-2 mb-1">
                  <Switch
                    checked={formData.calcLimit === -1}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        handleChange('_prevCalcLimit', formData.calcLimit > 0 ? formData.calcLimit : 100)
                        handleNumberChange('calcLimit', '-1')
                      } else {
                        handleNumberChange('calcLimit', String(formData._prevCalcLimit || 100))
                      }
                    }}
                  />
                  <span className="text-sm text-text-secondary">无限</span>
                </div>
                {formData.calcLimit !== -1 && (
                  <Input
                    type="number"
                    min="0"
                    value={formData.calcLimit}
                    onChange={(e) => handleNumberChange('calcLimit', e.target.value)}
                  />
                )}
              </div>
              <div className="space-y-2">
                <Label>物流模板</Label>
                <div className="flex items-center gap-2 mb-1">
                  <Switch
                    checked={formData.logisticsTemplate === -1}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        handleChange('_prevLogisticsTemplate', formData.logisticsTemplate > 0 ? formData.logisticsTemplate : 1)
                        handleNumberChange('logisticsTemplate', '-1')
                      } else {
                        handleNumberChange('logisticsTemplate', String(formData._prevLogisticsTemplate || 1))
                      }
                    }}
                  />
                  <span className="text-sm text-text-secondary">无限</span>
                </div>
                {formData.logisticsTemplate !== -1 && (
                  <Input
                    type="number"
                    min="0"
                    value={formData.logisticsTemplate}
                    onChange={(e) => handleNumberChange('logisticsTemplate', e.target.value)}
                  />
                )}
              </div>
              <div className="space-y-2">
                <Label>排序</Label>
                <Input
                  type="number"
                  min="1"
                  value={formData.sort}
                  onChange={(e) => handleNumberChange('sort', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>上架状态</Label>
                <div className="flex items-center gap-2 pt-2">
                  <Switch
                    checked={formData.status}
                    onCheckedChange={(checked) => handleChange('status', checked)}
                  />
                  <span className="text-sm text-text-secondary">
                    {formData.status ? '已上架' : '未上架'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label>描述</Label>
            <Textarea
              rows={2}
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              className="max-w-xl"
            />
          </div>

          <div className="space-y-2">
            <Label>特性列表（用 | 分隔）</Label>
            <Textarea
              rows={2}
              value={formData.features}
              onChange={(e) => handleChange('features', e.target.value)}
              placeholder="例如: 极速模式,无限物流模板,多物流比价"
              className="max-w-xl"
            />
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function PlanManagementPage() {
  const [plans, setPlans] = useState([])
  const [editingPlan, setEditingPlan] = useState(null)
  const [activeTab, setActiveTab] = useState('list')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  const fetchPlans = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await plansAPI.getAll(false)
      const list = Array.isArray(data) ? data : []
      setPlans(list.map(apiPlanToLocal))
    } catch (err) {
      setError('获取套餐列表失败')
      toast.error('获取套餐列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const loadPlans = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await plansAPI.getAll(false)
        if (!controller.signal.aborted) {
          const list = Array.isArray(data) ? data : []
          setPlans(list.map(apiPlanToLocal))
        }
      } catch {
        if (!controller.signal.aborted) {
          setError('获取套餐列表失败')
          toast.error('获取套餐列表失败')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }
    loadPlans()
    return () => controller.abort()
  }, [])

  const handleEdit = (planId) => {
    setEditingPlan(planId)
  }

  const handleCreate = async (_id, values) => {
    try {
      const apiData = localPlanToApi(values)
      await plansAPI.create(apiData)
      toast.success('套餐创建成功')
      setActiveTab('list')
      fetchPlans()
    } catch (err) {
      toast.error(err.response?.data?.detail || '创建套餐失败')
    }
  }

  const handleSave = async (planId, values) => {
    try {
      const apiData = localPlanToApi(values)
      await plansAPI.update(planId, apiData)
      toast.success('保存成功')
      setEditingPlan(null)
      fetchPlans()
    } catch (err) {
      toast.error(err.response?.data?.detail || '保存失败')
    }
  }

  const handleDelete = async (planId) => {
    try {
      await plansAPI.delete(planId)
      toast.success('套餐已删除')
      setDeleteConfirm(null)
      fetchPlans()
    } catch (err) {
      toast.error(err.response?.data?.detail || '删除失败')
    }
  }

  const handleToggle = async (planId) => {
    try {
      await plansAPI.toggleActive(planId)
      fetchPlans()
    } catch (err) {
      toast.error(err.response?.data?.detail || '状态切换失败')
    }
  }

  const handleCancel = () => {
    setEditingPlan(null)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text-primary font-headline tracking-tight">
        🎁 套餐管理 — 管理系统套餐
      </h1>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="list" className="gap-2">
            <List className="w-4 h-4" />
            套餐列表
          </TabsTrigger>
          <TabsTrigger value="add" className="gap-2">
            <Plus className="w-4 h-4" />
            新增套餐
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-4">
          {loading ? (
            <Card>
              <CardContent className="py-8 text-center text-zinc-400">加载中...</CardContent>
            </Card>
          ) : error ? (
            <Card>
              <CardContent className="py-8 text-center text-red-400">{error}</CardContent>
            </Card>
          ) : plans.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-zinc-400">暂无套餐数据</CardContent>
            </Card>
          ) : (
            plans.map(plan => (
              editingPlan === plan.id ? (
                <PlanEditForm 
                  key={plan.id} 
                  plan={plan} 
                  onSave={handleSave} 
                  onCancel={handleCancel}
                />
              ) : (
                <PlanCard 
                  key={plan.id} 
                  plan={plan} 
                  onEdit={handleEdit}
                  isEditing={editingPlan !== null}
                  onDelete={setDeleteConfirm}
                  onToggle={handleToggle}
                />
              )
            ))
          )}
        </TabsContent>

        <TabsContent value="add">
          <PlanEditForm
            plan={{
              id: null,
              code: '',
              name: '',
              displayPriceMonth: 0,
              displayPriceYear: 0,
              actualPriceMonth: 0,
              actualPriceYear: 0,
              testPriceMonth: 0,
              testPriceYear: 0,
              calcLimit: -1,
              logisticsTemplate: 1,
              sort: plans.length + 1,
              status: true,
              description: '',
              features: [],
            }}
            onSave={handleCreate}
            onCancel={() => setActiveTab('list')}
            isNew={true}
          />
        </TabsContent>
      </Tabs>
      
      <AlertDialog open={deleteConfirm !== null} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>确定要删除该套餐吗？此操作不可撤销。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => handleDelete(deleteConfirm)} className="bg-red-600 hover:bg-red-700">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default PlanManagementPage
