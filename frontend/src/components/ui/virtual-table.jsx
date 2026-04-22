import { useMemo, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { cn } from '@/lib/utils'

export function useVirtualRows({ count, getScrollElement, estimateSize, overscan, getItemKey }) {
  return useVirtualizer({
    count,
    getScrollElement,
    estimateSize: estimateSize ?? (() => 53),
    overscan: overscan ?? 8,
    getItemKey,
  })
}

export function VirtualTable({
  items,
  columns,
  getItemKey,
  rowHeight,
  overscan,
  maxHeight,
  loading,
  loadingContent,
  emptyContent,
  rowClassName,
  onRowClick,
  className,
}) {
  const scrollRef = useRef(null)
  const gridTemplateColumns = useMemo(
    () => columns.map((column) => column.width).join(' '),
    [columns],
  )

  const virtualizer = useVirtualRows({
    count: items.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight ?? 53,
    overscan,
    getItemKey: (index) => getItemKey(items[index]),
  })

  const virtualRows = virtualizer.getVirtualItems()
  const totalSize = virtualizer.getTotalSize()
  const containerStyle = maxHeight === undefined ? undefined : { maxHeight }
  const renderedRows =
    virtualRows.length > 0
      ? virtualRows
      : items.map((_, index) => ({ index, start: index * (rowHeight ?? 53) }))

  return (
    <div
      ref={scrollRef}
      className={cn('relative w-full overflow-auto rounded-md border', className)}
      style={containerStyle}
    >
      <div
        className="sticky top-0 z-20 grid border-b bg-muted text-sm font-medium shadow-sm"
        style={{ gridTemplateColumns }}
      >
        {columns.map((column) => (
          <div
            key={column.key}
            className={cn('px-4 py-3 text-left', column.headerClassName)}
          >
            {column.header}
          </div>
        ))}
      </div>

      {loading && items.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          {loadingContent}
        </div>
      ) : !loading && items.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          {emptyContent}
        </div>
      ) : (
        <div className="relative" style={{ height: totalSize }}>
          {renderedRows.map((virtualRow) => {
            const item = items[virtualRow.index]
            const resolvedRowClassName =
              typeof rowClassName === 'function' ? rowClassName(item) : rowClassName
            const rowKey = getItemKey(item)

            return (
              <div
                key={rowKey}
                ref={virtualizer.measureElement}
                data-index={virtualRow.index}
                data-row
                className={cn(
                  'absolute left-0 top-0 grid w-full items-center border-b hover:bg-muted/30',
                  resolvedRowClassName,
                  onRowClick && 'cursor-pointer',
                )}
                style={{
                  transform: `translateY(${virtualRow.start}px)`,
                  gridTemplateColumns,
                }}
                onClick={onRowClick ? () => onRowClick(item) : undefined}
              >
                {columns.map((column) => (
                  <div
                    key={column.key}
                    data-cell
                    className={cn('px-4 py-3 text-sm', column.cellClassName)}
                  >
                    {column.render(item, virtualRow.index)}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
