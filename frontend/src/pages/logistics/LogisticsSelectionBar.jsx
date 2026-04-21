import React from 'react'
import { Trash2 } from 'lucide-react'
import { Button } from '../../components/ui/button'

export default function LogisticsSelectionBar({ selectedCount, onClearSelection, onOpenBatchDelete }) {
  if (selectedCount <= 0) return null

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-surface-high border border-surface-highest rounded-lg px-6 py-3 shadow-lg">
      <span className="text-sm text-text-primary">已选 {selectedCount} 项</span>
      <Button variant="ghost" size="sm" onClick={onClearSelection} className="transition-all duration-200">
        清除
      </Button>
      <Button variant="destructive" size="sm" onClick={onOpenBatchDelete} className="transition-all duration-200">
        <Trash2 className="h-4 w-4 mr-1" />
        批量删除
      </Button>
    </div>
  )
}
