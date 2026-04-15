import React, { useState, useRef } from 'react'
import { Upload, ArrowRight, CheckCircle2, Loader2, RefreshCcw } from 'lucide-react'
import { toast } from 'sonner'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Label } from '../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table'
import { productImportAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'

const PRODUCT_FIELDS = [
  { id: 'name', label: '产品名称 (必填)' },
  { id: 'cost_cny', label: '采购成本' },
  { id: 'weight_g', label: '重量 (克)' },
  { id: 'length_cm', label: '长 (厘米)' },
  { id: 'width_cm', label: '宽 (厘米)' },
  { id: 'height_cm', label: '高 (厘米)' },
  { id: 'allow_battery', label: '是否带电 (是/否)' },
  { id: 'allow_liquid', label: '是否液体 (是/否)' },
]

const PREVIEW_DISPLAY_LIMIT = 10

export default function ProductImportPage() {
  const { user, hasEnterpriseAccess } = useAuthStore()
  const [step, setStep] = useState(1)
  const [isUploading, setIsUploading] = useState(false)
  const [isConfirming, setIsConfirming] = useState(false)

  const [columns, setColumns] = useState([])
  const [preview, setPreview] = useState([])
  const previewDisplayRows = preview.slice(0, PREVIEW_DISPLAY_LIMIT)
  
  const [columnMapping, setColumnMapping] = useState({})
  const [onDuplicate, setOnDuplicate] = useState('skip')
  
  const [importResult, setImportResult] = useState(null)
  
  const fileInputRef = useRef(null)
  const canImport = hasEnterpriseAccess()
  const subscriptionType = user?.subscription_type || user?.user_type || 'free'

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    setIsUploading(true)
    try {
      const data = await productImportAPI.preview(formData)
      const nextColumns = (data.columns || []).filter(c => c && c.trim())
      const nextPreview = data.preview_rows || []
      setColumns(nextColumns)
      setPreview(nextPreview)
      
      const initialMapping = {}
      PRODUCT_FIELDS.forEach(field => {
        const exactMatch = nextColumns.find(c => 
          c.toLowerCase() === field.id.toLowerCase() || 
          c === field.label.split(' ')[0]
        )
        if (exactMatch) {
          initialMapping[field.id] = exactMatch
        }
      })
      setColumnMapping(initialMapping)
      setStep(2)
      toast.success('文件解析成功，请确认列映射')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '文件解析失败，请检查文件格式')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleMappingChange = (fieldId, columnName) => {
    setColumnMapping(prev => ({
      ...prev,
      [fieldId]: columnName === 'none' ? null : columnName
    }))
  }

  const handleConfirmImport = async () => {
    if (!columnMapping.name) {
      toast.error('必须映射"产品名称"列')
      return
    }

    setIsConfirming(true)
    try {
      const data = await productImportAPI.confirm({
        rows: preview,
        column_mapping: columnMapping,
        conflict_action: onDuplicate
      })
      setImportResult(data)
      setStep(3)
      toast.success('导入完成')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '导入处理失败')
    } finally {
      setIsConfirming(false)
    }
  }

  const resetProcess = () => {
    setStep(1)
    setColumns([])
    setPreview([])
    setColumnMapping({})
    setImportResult(null)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">产品批量导入</h1>
        <p className="text-sm text-text-secondary mt-1">支持 Excel (.xlsx, .xls) 格式文件导入</p>
      </div>

      {!canImport ? (
        <Card className="border-amber-200 bg-amber-50/80 shadow-sm">
          <CardContent className="py-10">
            <div className="space-y-2 text-center">
              <h2 className="text-lg font-semibold text-amber-900">升级到企业版，解锁 Excel 产品导入</h2>
              <p className="text-sm text-amber-800">当前订阅为 {subscriptionType}，企业版及以上支持 Excel 预览与正式导入。</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>

      {step === 1 && (
        <Card className="border-dashed border-2 bg-surface-container">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <Upload className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-lg font-medium mb-2">上传产品数据表</h3>
            <p className="text-sm text-text-muted mb-6 max-w-sm">
              请确保包含产品名称、重量、尺寸等基础数据。系统将自动解析表头，您可以在下一步进行字段映射。
            </p>
            <input
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileUpload}
            />
            <Button 
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              {isUploading ? '正在解析文件...' : '选择 Excel 文件'}
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>字段映射</CardTitle>
              <p className="text-sm text-text-muted">
                将系统产品字段与您 Excel 表中的列进行匹配。
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {PRODUCT_FIELDS.map((field) => (
                  <div key={field.id} className="space-y-2">
                    <Label className={field.id === 'name' ? "font-semibold" : ""}>
                      {field.label}
                    </Label>
                    <Select 
                      value={columnMapping[field.id] || 'none'}
                      onValueChange={(val) => handleMappingChange(field.id, val)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="不映射" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">-- 不映射 --</SelectItem>
                        {columns.map(col => (
                          <SelectItem key={col} value={col}>{col}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>导入设置</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Label>遇到重名产品时：</Label>
                <RadioGroup value={onDuplicate} onValueChange={setOnDuplicate}>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="skip" id="skip" />
                    <Label htmlFor="skip" className="font-normal text-text-secondary">跳过 (保留原有产品)</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="overwrite" id="overwrite" />
                    <Label htmlFor="overwrite" className="font-normal text-text-secondary">覆盖 (更新产品信息)</Label>
                  </div>
                </RadioGroup>
              </div>
            </CardContent>
          </Card>

          {preview.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>数据预览 (前 {previewDisplayRows.length} 行)</CardTitle>
                <p className="text-sm text-text-muted">共 {preview.length} 条数据</p>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {columns.slice(0, 20).map((col) => (
                        <TableHead key={col} className="whitespace-nowrap">{col}</TableHead>
                      ))}
                      {columns.length > 20 && (
                        <TableHead className="whitespace-nowrap text-text-muted">…还有 {columns.length - 20} 列</TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewDisplayRows.map((row, idx) => (
                      <TableRow key={row.name || row[columns[0]] || `preview-row-${idx}`}>
                        {columns.slice(0, 20).map((col) => (
                          <TableCell key={col} className="whitespace-nowrap">
                            {row[col] !== null && row[col] !== undefined ? String(row[col]) : ''}
                          </TableCell>
                        ))}
                        {columns.length > 20 && (
                          <TableCell className="whitespace-nowrap text-text-muted">…</TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
              <div className="bg-surface-container/50 flex justify-between py-4 px-6 border-t border-surface-high">
                <Button variant="outline" onClick={resetProcess}>取消导入</Button>
                <Button onClick={handleConfirmImport} disabled={isConfirming}>
                  {isConfirming ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                  )}
                  开始导入
                </Button>
              </div>
            </Card>
          )}
        </div>
      )}

      {step === 3 && importResult && (
        <Card className="border-status-success">
          <CardHeader className="text-center pt-10">
            <div className="w-16 h-16 rounded-full bg-status-success/20 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-10 h-10 text-status-success" />
            </div>
            <CardTitle className="text-2xl text-text-primary">导入处理完成</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center py-6">
              <div className="p-4 bg-surface-container rounded-lg border border-surface-high">
                <div className="text-3xl font-semibold text-primary">{importResult.imported || 0}</div>
                <div className="text-sm text-text-secondary mt-1">成功导入</div>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-surface-high">
                <div className="text-3xl font-semibold text-status-warning">{importResult.skipped || 0}</div>
                <div className="text-sm text-text-secondary mt-1">跳过行数</div>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-surface-high">
                <div className="text-3xl font-semibold text-status-info">{importResult.overwritten || 0}</div>
                <div className="text-sm text-text-secondary mt-1">覆盖更新</div>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-surface-high">
                <div className="text-sm font-semibold text-status-error">{importResult.errors || 0}</div>
                <div className="text-sm text-text-secondary mt-1">失败行数</div>
              </div>
            </div>
          </CardContent>
          <div className="flex justify-center pb-8">
            <Button onClick={resetProcess}>
              <RefreshCcw className="w-4 h-4 mr-2" />
              继续导入
            </Button>
          </div>
        </Card>
      )}
        </>
      )}
    </div>
  )
}
