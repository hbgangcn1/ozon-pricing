import React from 'react'
import { Plus } from 'lucide-react'
import { Button } from '../components/ui/button'
import LogisticsDialogs from './logistics/LogisticsDialogs'
import LogisticsFilters from './logistics/LogisticsFilters'
import LogisticsFormDialog from './logistics/LogisticsFormDialog'
import LogisticsPagination from './logistics/LogisticsPagination'
import LogisticsSelectionBar from './logistics/LogisticsSelectionBar'
import LogisticsTabs from './logistics/LogisticsTabs'
import { useLogisticsPage } from './logistics/useLogisticsPage'
import OverflowReselectModal from '../components/OverflowReselectModal'

export default function LogisticsPage() {
  const logistics = useLogisticsPage()

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-headline tracking-tight">物流规则管理</h1>
        <Button onClick={logistics.handleAdd} className="transition-all duration-200">
          <Plus className="h-4 w-4 mr-1" />
          添加物流规则
        </Button>
      </div>

      <LogisticsFilters
        filterFulfillment={logistics.filterFulfillment}
        filterDestination={logistics.filterDestination}
        onFulfillmentChange={logistics.handleFulfillmentChangeFilter}
        onDestinationChange={logistics.handleDestinationChangeFilter}
      />

      {logistics.loading && (
        <div className="flex items-center justify-center py-8 text-text-secondary">
          <span className="animate-spin mr-2">⏳</span>
          加载中...
        </div>
      )}

      <LogisticsTabs
        activeTab={logistics.activeTab}
        logistics={logistics.logistics}
        selectedIds={logistics.selectedIds}
        togglingIds={logistics.togglingIds}
        onTabChange={logistics.handleTabChange}
        onSelectAll={logistics.handleSelectAll}
        onClearSelection={logistics.handleClearSelection}
        onToggleSelect={logistics.toggleSelect}
        onEdit={logistics.handleEdit}
        onDelete={logistics.setDeleteConfirmId}
        onToggleActive={logistics.handleToggleActive}
        onToggleTransport={logistics.handleToggleTransport}
      />

      <LogisticsFormDialog
        dialogOpen={logistics.dialogOpen}
        editingItem={logistics.editingItem}
        form={logistics.form}
        onOpenChange={logistics.setDialogOpen}
        onSubmit={logistics.handleSubmit}
        onFulfillmentChange={logistics.handleFulfillmentChange}
        onFormFieldChange={logistics.setFormField}
      />

      <LogisticsPagination
        currentPage={logistics.currentPage}
        pageSize={logistics.pageSize}
        total={logistics.total}
        totalPages={logistics.totalPages}
        onPageSizeChange={logistics.handlePageSizeChange}
        onPrevPage={logistics.handlePrevPage}
        onNextPage={logistics.handleNextPage}
        onPageChange={logistics.setCurrentPage}
      />

      <LogisticsDialogs
        deleteConfirmId={logistics.deleteConfirmId}
        batchDeleteDialogOpen={logistics.batchDeleteDialogOpen}
        selectedCount={logistics.selectedIds.size}
        onDeleteDialogChange={logistics.handleDeleteDialogChange}
        onBatchDeleteDialogChange={logistics.setBatchDeleteDialogOpen}
        onConfirmDelete={logistics.confirmDelete}
        onConfirmBatchDelete={logistics.handleBatchDelete}
      />

      <LogisticsSelectionBar
        selectedCount={logistics.selectedIds.size}
        onClearSelection={logistics.handleClearSelection}
        onOpenBatchDelete={() => logistics.setBatchDeleteDialogOpen(true)}
      />

      <OverflowReselectModal
        items={logistics.logistics}
        onCompleted={logistics.fetchLogistics}
      />
    </div>
  )
}
