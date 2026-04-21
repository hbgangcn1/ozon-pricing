import React from 'react'
import { Checkbox } from '../../components/ui/checkbox'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'
import LogisticsList from './LogisticsList'

function LogisticsTabPanel({ logistics, selectedIds, onSelectAll, onClearSelection, ...listProps }) {
  return (
    <>
      {logistics.length > 0 && (
        <div className="flex items-center gap-3 mb-3 px-1">
          <Checkbox
            checked={logistics.length > 0 && logistics.every((item) => selectedIds.has(item.id))}
            onCheckedChange={(checked) => {
              if (checked) {
                onSelectAll(logistics)
              } else {
                onClearSelection()
              }
            }}
            aria-label="全选当前页"
          />
          <span className="text-sm text-text-secondary select-none">全选当前页</span>
        </div>
      )}
      <LogisticsList items={logistics} selectedIds={selectedIds} {...listProps} />
    </>
  )
}

export default function LogisticsTabs({ activeTab, onTabChange, logistics, selectedIds, ...listProps }) {
  return (
    <Tabs value={activeTab} onValueChange={onTabChange}>
      <TabsList className="mb-4">
        <TabsTrigger value="land">陆运</TabsTrigger>
        <TabsTrigger value="air">空运</TabsTrigger>
      </TabsList>
      <TabsContent value="land">
        <LogisticsTabPanel logistics={logistics} selectedIds={selectedIds} {...listProps} />
      </TabsContent>
      <TabsContent value="air">
        <LogisticsTabPanel logistics={logistics} selectedIds={selectedIds} {...listProps} />
      </TabsContent>
    </Tabs>
  )
}
