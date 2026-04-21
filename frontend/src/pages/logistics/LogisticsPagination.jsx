import React from 'react'
import { Button } from '../../components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { buildPaginationItems } from './logisticsUtils'

export default function LogisticsPagination({
  currentPage,
  pageSize,
  total,
  totalPages,
  onPageSizeChange,
  onPrevPage,
  onNextPage,
  onPageChange,
}) {
  const pages = buildPaginationItems(currentPage, totalPages)

  return (
    <div className="flex items-center justify-between border-t border-surface-high pt-4 mt-6">
      <div className="flex items-center text-sm text-text-secondary">共 {total} 条</div>
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          <span className="text-sm text-text-secondary">每页</span>
          <Select value={String(pageSize)} onValueChange={onPageSizeChange}>
            <SelectTrigger className="h-8 w-[70px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
              <SelectItem value="200">200</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-sm text-text-secondary">条</span>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" className="h-8 px-3" disabled={currentPage === 1} onClick={onPrevPage}>
            上一页
          </Button>
          <div className="flex items-center space-x-1">
            {pages.map((page) => {
              if (typeof page === 'string') {
                return <span key={page} className="px-2 text-text-muted">...</span>
              }

              return (
                <Button
                  key={page}
                  variant={currentPage === page ? 'default' : 'ghost'}
                  size="sm"
                  className={`h-8 w-8 p-0 ${currentPage === page ? '' : 'text-text-secondary hover:text-text-primary'}`}
                  onClick={() => onPageChange(page)}
                >
                  {page}
                </Button>
              )
            })}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8 px-3"
            disabled={currentPage === totalPages || totalPages === 0}
            onClick={onNextPage}
          >
            下一页
          </Button>
        </div>
      </div>
    </div>
  )
}
