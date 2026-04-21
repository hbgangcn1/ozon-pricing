import React from 'react'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { FILTER_DESTINATION_OPTIONS } from './logisticsConstants'

export default function LogisticsFilters({
  filterFulfillment,
  filterDestination,
  onFulfillmentChange,
  onDestinationChange,
}) {
  return (
    <div className="flex flex-wrap gap-4 pt-2">
      <div className="flex items-center gap-2">
        <Label className="text-sm font-medium">发货类型:</Label>
        <Select value={filterFulfillment} onValueChange={onFulfillmentChange}>
          <SelectTrigger className="w-[140px] h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            <SelectItem value="rfbs">rFBS</SelectItem>
            <SelectItem value="fbp">FBP</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-2">
        <Label className="text-sm font-medium">目的国:</Label>
        <Select value={filterDestination} onValueChange={onDestinationChange}>
          <SelectTrigger className="w-[140px] h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            {FILTER_DESTINATION_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
