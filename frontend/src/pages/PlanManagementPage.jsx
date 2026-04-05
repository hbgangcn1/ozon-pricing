import { useState } from 'react'
import { Edit, Save, X, Check, Plus, List, Settings } from 'lucide-react'
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

const initialPlans = {
  free: {
    id: 'free',
    name: '免费版',
    displayPriceMonth: 0,
    displayPriceYear: 0,
    actualPriceMonth: 0,
    actualPriceYear: 0,
    testPriceMonth: 0,
    testPriceYear: 0,
    calcLimit: 10,
    logisticsTemplate: 1,
    sort: 1,
    status: true,
    description: '免费基础版本，适合新手试用',
    features: ['极速模式', '基础物流模板', '每日10次计算'],
  },
  efficiency: {
    id: 'efficiency',
    name: '效率版',
    displayPriceMonth: 9.9,
    displayPriceYear: 99,
    actualPriceMonth: 9.9,
    actualPriceYear: 99,
    testPriceMonth: 0.01,
    testPriceYear: 0.1,
    calcLimit: -1,
    logisticsTemplate: 3,
    sort: 2,
    status: true,
    description: '适合中小型卖家使用',
    features: ['无限极速模式', '3个物流模板', '无限计算次数'],
  },
  professional: {
    id: 'professional',
    name: '专业版',
    displayPriceMonth: 149,
    displayPriceYear: 1499,
    actualPriceMonth: 149,
    actualPriceYear: 1499,
    testPriceMonth: 0.1,
    testPriceYear: 1,
    calcLimit: -1,
    logisticsTemplate: -1,
    sort: 3,
    status: true,
    description: '适合专业卖家，支持精准模式',
    features: ['极速+精准模式', '无限物流模板', '多物流比价', '无限计算次数'],
  },
  enterprise: {
    id: 'enterprise',
    name: '企业版',
    displayPriceMonth: 999,
    displayPriceYear: 0,
    actualPriceMonth: 999,
    actualPriceYear: 0,
    testPriceMonth: 1,
    testPriceYear: 0,
    calcLimit: -1,
    logisticsTemplate: -1,
    sort: 4,
    status: false,
    description: '适合大型企业，功能最全面',
    features: ['专业版所有功能', 'API级活动监控', '专属客服', '开发中...'],
  },
}

function PlanCard({ plan, onEdit, isEditing }) {
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
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => onEdit(plan.id)}
            disabled={isEditing}
          >
            <Edit className="w-4 h-4 mr-2" />
            编辑
          </Button>
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
              <TableCell>¥{plan.displayPriceMonth}</TableCell>
              <TableCell>¥{plan.displayPriceYear || '-'}</TableCell>
              <TableCell>¥{plan.actualPriceMonth}</TableCell>
              <TableCell>¥{plan.actualPriceYear || '-'}</TableCell>
              <TableCell>¥{plan.testPriceMonth}</TableCell>
              <TableCell>¥{plan.testPriceYear || '-'}</TableCell>
              <TableCell>{plan.calcLimit === -1 ? '无限' : `${plan.calcLimit}次/月`}</TableCell>
              <TableCell>{plan.logisticsTemplate === -1 ? '无限' : plan.logisticsTemplate}</TableCell>
              <TableCell>{plan.sort}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        
        <div className="mt-4">
          <p className="text-text-secondary text-sm">{plan.description}</p>
        </div>
        
        <div className="mt-4 flex flex-wrap gap-2">
          {plan.features.map((f, i) => (
            <Badge key={i} variant="secondary">{f}</Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function PlanEditForm({ plan, onSave, onCancel }) {
  const [formData, setFormData] = useState({
    ...plan,
    features: Array.isArray(plan.features) ? plan.features.join(', ') : ''
  })

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleNumberChange = (field, value) => {
    const numValue = value === '' ? 0 : parseFloat(value)
    setFormData(prev => ({ ...prev, [field]: numValue }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const featuresArray = formData.features 
      ? formData.features.split(',').map(f => f.trim()).filter(f => f)
      : []
    onSave(plan.id, { ...formData, features: featuresArray })
  }

  return (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>编辑套餐: {plan.name}</CardTitle>
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
                <Input
                  type="number"
                  min="-1"
                  value={formData.calcLimit}
                  onChange={(e) => handleNumberChange('calcLimit', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>物流模板</Label>
                <Input
                  type="number"
                  min="-1"
                  value={formData.logisticsTemplate}
                  onChange={(e) => handleNumberChange('logisticsTemplate', e.target.value)}
                />
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
            <Label>特性列表（用逗号分隔）</Label>
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
  const [plans, setPlans] = useState(initialPlans)
  const [editingPlan, setEditingPlan] = useState(null)
  const [activeTab, setActiveTab] = useState('list')

  const handleEdit = (planId) => {
    setEditingPlan(planId)
  }

  const handleSave = (planId, values) => {
    setPlans(prev => ({
      ...prev,
      [planId]: { ...prev[planId], ...values }
    }))
    setEditingPlan(null)
    toast.success('保存成功')
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
          {Object.values(plans).map(plan => (
            editingPlan === plan.id ? (
              <PlanEditForm 
                key={plan.id} 
                plan={plans[plan.id]} 
                onSave={handleSave} 
                onCancel={handleCancel}
              />
            ) : (
              <PlanCard 
                key={plan.id} 
                plan={plan} 
                onEdit={handleEdit}
                isEditing={editingPlan !== null}
              />
            )
          ))}
        </TabsContent>

        <TabsContent value="add">
          <Card>
            <CardHeader>
              <CardTitle>➕ 新增套餐</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-text-secondary">新增套餐功能开发中...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default PlanManagementPage
