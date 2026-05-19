import React from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import PricingForm from './pricing/PricingForm'
import ProductDialogs from './pricing/ProductDialogs'
import PricingResultPanel from './pricing/PricingResultPanel'
import { usePricingCalculation } from './pricing/usePricingCalculation'

export default function PricingPage() {
  const { user, hasProfessionalAccess, isInTrial } = useAuthStore()
  const pricing = usePricingCalculation(user)
  const inTrial = isInTrial()
  const hasProAccess = hasProfessionalAccess()

  const isPreciseDisabled = (user?.user_type === 'free' || user?.user_type === 'efficiency') && !inTrial
  const preciseLabel = isPreciseDisabled ? '精准模式（限专业版/企业版）' : '精准模式'

  const isLimitedCalcTier = !hasProAccess
    && user?.subscription_type !== 'efficiency'
    && user?.user_type !== 'efficiency'

  const remainingCalcText = (() => {
    const rc = user?.remaining_calculations
    if (rc > 0) return `剩余 ${rc} 次计算`
    if (rc === 0) return '今日计算次数已用完，请明天再来或升级套餐'
    return '剩余 10 次计算'
  })()

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold font-headline tracking-tight mb-6">物流定价计算</h1>

      {pricing.hasLogisticsRules === false && (
        <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 flex items-center gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-amber-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <title>警告</title>
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <span className="text-amber-200 text-sm font-medium">请先添加物流规则</span>
          <Link to="/logistics" className="ml-auto text-sm text-indigo-400 hover:text-indigo-300 underline">
            前往物流管理
          </Link>
        </div>
      )}

      {isLimitedCalcTier && (
        <div className="text-xs text-muted-foreground text-center mb-2">
          {remainingCalcText}
        </div>
      )}

      <PricingForm
        activeTab={pricing.activeTab}
        setActiveTab={pricing.setActiveTab}
        preciseLabel={preciseLabel}
        fastForm={pricing.fastForm}
        setFastForm={pricing.setFastForm}
        preciseForm={pricing.preciseForm}
        setPreciseForm={pricing.setPreciseForm}
        products={pricing.products}
        commissionCategories={pricing.commissionCategories}
        loading={pricing.loading}
        onOpenProductList={() => pricing.setProductListDialogOpen(true)}
        onProductSelect={pricing.handleProductSelect}
        onSavePreciseProduct={pricing.handleSavePreciseProduct}
        onFastCalculate={pricing.handleFastCalculate}
        onPreciseCalculate={pricing.handlePreciseCalculate}
      />

      <PricingResultPanel
        activeTab={pricing.activeTab}
        fastResult={pricing.fastResult}
        preciseResult={pricing.preciseResult}
        groupedResult={pricing.groupedResult}
        groupActiveTab={pricing.groupActiveTab}
        setGroupActiveTab={pricing.setGroupActiveTab}
        cisActiveTab={pricing.cisActiveTab}
        setCisActiveTab={pricing.setCisActiveTab}
        showBreakeven={pricing.showBreakeven}
        setShowBreakeven={pricing.setShowBreakeven}
      />

      <ProductDialogs
        products={pricing.products}
        commissionCategories={pricing.commissionCategories}
        productListDialogOpen={pricing.productListDialogOpen}
        onProductListDialogChange={pricing.handleProductListDialogChange}
        productDialogOpen={pricing.productDialogOpen}
        onProductDialogChange={pricing.setProductDialogOpen}
        editingProduct={pricing.editingProduct}
        productForm={pricing.productForm}
        setProductForm={pricing.setProductForm}
        selectedProductIds={pricing.selectedProductIds}
        allSelected={pricing.allSelected}
        someSelected={pricing.someSelected}
        onSelectAll={pricing.handleSelectAll}
        onSelectProduct={pricing.handleSelectProduct}
        onEditProduct={pricing.handleEditProduct}
        onDeleteProduct={pricing.handleDeleteProduct}
        onSaveProduct={pricing.handleSaveProduct}
        deleteConfirmOpen={pricing.deleteConfirmOpen}
        onDeleteConfirmChange={pricing.setDeleteConfirmOpen}
        pendingDeleteProduct={pricing.pendingDeleteProduct}
        onConfirmDelete={pricing.confirmDeleteProduct}
        batchDeleteConfirmOpen={pricing.batchDeleteConfirmOpen}
        onBatchDeleteConfirmChange={pricing.setBatchDeleteConfirmOpen}
        onOpenBatchDelete={() => pricing.setBatchDeleteConfirmOpen(true)}
        onBatchDelete={pricing.handleBatchDelete}
      />
    </div>
  )
}
