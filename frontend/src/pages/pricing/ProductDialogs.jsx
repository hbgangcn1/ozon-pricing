import React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../../components/ui/alert-dialog'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Checkbox } from '../../components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '../../components/ui/radio-group'
import RateInput from './RateInput'

function ProductDimensionEditor({ productForm, setProductForm }) {
  if (productForm.is_cylinder === 'regular') {
    return (
      <div className="grid grid-cols-3 gap-3">
        <div>
          <Label>长（厘米）</Label>
          <Input type="number" value={productForm.length_cm} onChange={(event) => setProductForm({ ...productForm, length_cm: event.target.value })} />
        </div>
        <div>
          <Label>宽（厘米）</Label>
          <Input type="number" value={productForm.width_cm} onChange={(event) => setProductForm({ ...productForm, width_cm: event.target.value })} />
        </div>
        <div>
          <Label>高（厘米）</Label>
          <Input type="number" value={productForm.height_cm} onChange={(event) => setProductForm({ ...productForm, height_cm: event.target.value })} />
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <Label>圆柱直径（厘米）</Label>
        <Input type="number" value={productForm.cylinder_diameter} onChange={(event) => setProductForm({ ...productForm, cylinder_diameter: event.target.value })} />
      </div>
      <div>
        <Label>圆柱长度（厘米）</Label>
        <Input type="number" value={productForm.cylinder_length} onChange={(event) => setProductForm({ ...productForm, cylinder_length: event.target.value })} />
      </div>
    </div>
  )
}

function ProductListDialog({
  products,
  productListDialogOpen,
  onProductListDialogChange,
  selectedProductIds,
  allSelected,
  someSelected,
  onSelectAll,
  onSelectProduct,
  onEditProduct,
  onDeleteProduct,
  onOpenBatchDelete,
}) {
  return (
    <Dialog open={productListDialogOpen} onOpenChange={onProductListDialogChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>产品列表</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {products.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">暂无产品，请先创建</p>
          ) : (
            <>
              <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10 mb-2">
                <Checkbox checked={allSelected ? true : someSelected ? 'indeterminate' : false} onCheckedChange={onSelectAll} />
                <span className="text-sm text-zinc-400">全选</span>
              </div>
              {products.map((product) => (
                <div key={product.id} className="flex items-center justify-between p-3 border rounded bg-card">
                  <Checkbox checked={selectedProductIds.has(product.id)} onCheckedChange={() => onSelectProduct(product.id)} className="mr-3" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{product.name}</div>
                    <div className="text-xs text-muted-foreground">
                      ¥{Number(product.unit_price).toFixed(2)} / {product.weight_g}g
                      {product.is_cylinder ? ' / 圆柱' : ' / 常规'}
                    </div>
                  </div>
                  <div className="flex gap-1 ml-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 transition-all duration-200"
                      data-testid={`product-edit-${product.id}`}
                      aria-label={`编辑产品 ${product.name}`}
                      onClick={() => {
                        onProductListDialogChange(false)
                        onEditProduct(product)
                      }}
                    >
                      ✏️
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 transition-all duration-200"
                      data-testid={`product-delete-${product.id}`}
                      aria-label={`删除产品 ${product.name}`}
                      onClick={() => onDeleteProduct(product)}
                    >
                      🗑️
                    </Button>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
        <DialogFooter>
          {selectedProductIds.size > 0 && (
            <button
              type="button"
              onClick={onOpenBatchDelete}
              className="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors mr-auto"
            >
              删除选中 ({selectedProductIds.size})
            </button>
          )}
          <Button variant="outline" onClick={() => onProductListDialogChange(false)} className="transition-all duration-200">关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ProductEditorDialog({
  commissionCategories,
  productDialogOpen,
  onProductDialogChange,
  editingProduct,
  productForm,
  setProductForm,
  onSaveProduct,
}) {
  return (
    <Dialog open={productDialogOpen} onOpenChange={onProductDialogChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editingProduct ? '编辑产品' : '新建产品'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          <div>
            <Label>产品名称 <span className="text-status-error">*</span></Label>
            <Input
              data-testid="product-form-name"
              aria-label="产品名称"
              value={productForm.name}
              onChange={(event) => setProductForm({ ...productForm, name: event.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>进货单价（元） <span className="text-status-error">*</span></Label>
              <Input type="number" step="0.01" value={productForm.unit_price} onChange={(event) => setProductForm({ ...productForm, unit_price: event.target.value })} />
            </div>
            <div>
              <Label>重量（克） <span className="text-status-error">*</span></Label>
              <Input type="number" value={productForm.weight_g} onChange={(event) => setProductForm({ ...productForm, weight_g: event.target.value })} />
            </div>
          </div>
          <div className="space-y-1">
            <Label>包装类型</Label>
            <RadioGroup value={productForm.is_cylinder} onValueChange={(value) => setProductForm({ ...productForm, is_cylinder: value })} className="flex gap-4">
              <div className="flex items-center gap-1.5">
                <RadioGroupItem value="regular" id="form-pkg-regular" />
                <Label htmlFor="form-pkg-regular" className="text-sm cursor-pointer">常规包装</Label>
              </div>
              <div className="flex items-center gap-1.5">
                <RadioGroupItem value="cylinder" id="form-pkg-cylinder" />
                <Label htmlFor="form-pkg-cylinder" className="text-sm cursor-pointer">圆柱包装</Label>
              </div>
            </RadioGroup>
          </div>
          <ProductDimensionEditor productForm={productForm} setProductForm={setProductForm} />
          <div className="flex gap-4">
            <div className="flex items-center gap-2 text-sm">
              <Checkbox checked={productForm.has_battery} aria-label="产品含电池" onCheckedChange={(value) => setProductForm({ ...productForm, has_battery: !!value })} />
              含电池
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Checkbox checked={productForm.has_liquid} aria-label="产品含液体" onCheckedChange={(value) => setProductForm({ ...productForm, has_liquid: !!value })} />
              含液体
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>贴标费用（元）</Label>
              <Input type="number" step="0.01" value={productForm.labeling_fee} onChange={(event) => setProductForm({ ...productForm, labeling_fee: event.target.value })} />
            </div>
            <div>
              <Label>供货方不包邮运费（元）</Label>
              <Input type="number" step="0.01" value={productForm.shipping_fee} onChange={(event) => setProductForm({ ...productForm, shipping_fee: event.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">佣金类目</Label>
              <Select value={productForm.commission_category_id} onValueChange={(value) => setProductForm({ ...productForm, commission_category_id: value })}>
                <SelectTrigger className="h-8">
                  <SelectValue placeholder="选择佣金类目" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">不使用类目(0%)</SelectItem>
                  {commissionCategories.map((category) => (
                    <SelectItem key={category.id} value={String(category.id)}>{category.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <RateInput label="运营利润率(%)" value={productForm.target_profit_margin} onChange={(value) => setProductForm({ ...productForm, target_profit_margin: value })} defaultVal="0" step="1" />
            <RateInput label="推广费率(%)" value={productForm.promotion_cost_rate} onChange={(value) => setProductForm({ ...productForm, promotion_cost_rate: value })} defaultVal="0" step="1" />
            <RateInput label="打款提现费率(%)" value={productForm.withdrawal_fee_rate} onChange={(value) => setProductForm({ ...productForm, withdrawal_fee_rate: value })} defaultVal="0" step="1" />
            <RateInput label="收单手续费率(%)" value={productForm.payment_processing_fee} onChange={(value) => setProductForm({ ...productForm, payment_processing_fee: value })} defaultVal="0" step="1" />
            <RateInput label="历史退货率(%)" value={productForm.return_rate} onChange={(value) => setProductForm({ ...productForm, return_rate: value })} defaultVal="0" step="1" />
            <RateInput label="增值税率(%)" value={productForm.vat_rate} onChange={(value) => setProductForm({ ...productForm, vat_rate: value })} defaultVal="0" step="1" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onProductDialogChange(false)} className="transition-all duration-200">取消</Button>
          <Button onClick={onSaveProduct} className="transition-all duration-200">{editingProduct ? '保存修改' : '创建'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ProductDialogs(props) {
  return (
    <>
      <ProductListDialog {...props} />

      <AlertDialog open={props.deleteConfirmOpen} onOpenChange={props.onDeleteConfirmChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除产品「{props.pendingDeleteProduct?.name}」吗？此操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => props.onDeleteConfirmChange(false)}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={props.onConfirmDelete} className="bg-status-error hover:bg-status-error/85">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={props.batchDeleteConfirmOpen} onOpenChange={props.onBatchDeleteConfirmChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认批量删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除选中的 {props.selectedProductIds.size} 个产品吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={props.onBatchDelete} className="bg-status-error hover:bg-status-error/85">确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ProductEditorDialog {...props} />
    </>
  )
}
