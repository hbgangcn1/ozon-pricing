import React from 'react'
import { Button } from '../../components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog'
import LogisticsBasicSection from './LogisticsBasicSection'
import LogisticsPricingSection from './LogisticsPricingSection'
import LogisticsRestrictionsSection from './LogisticsRestrictionsSection'

export default function LogisticsFormDialog({
  dialogOpen,
  editingItem,
  form,
  onOpenChange,
  onSubmit,
  onFulfillmentChange,
  onFormFieldChange,
}) {
  return (
    <Dialog open={dialogOpen} onOpenChange={onOpenChange}>
      <DialogContent className="w-full max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editingItem ? '编辑物流规则' : '添加物流规则'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-6">
          <LogisticsBasicSection
            form={form}
            onFormFieldChange={onFormFieldChange}
            onFulfillmentChange={onFulfillmentChange}
          />
          <LogisticsPricingSection form={form} onFormFieldChange={onFormFieldChange} />
          <LogisticsRestrictionsSection form={form} onFormFieldChange={onFormFieldChange} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="transition-all duration-200">取消</Button>
          <Button onClick={onSubmit} className="transition-all duration-200">{editingItem ? '更新' : '创建'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
