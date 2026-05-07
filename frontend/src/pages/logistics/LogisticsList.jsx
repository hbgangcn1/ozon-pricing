import React from 'react'
import { ArrowLeftRight, Droplets, MoreHorizontal, Pencil, Trash2, Zap } from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import { Checkbox } from '../../components/ui/checkbox'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../components/ui/dropdown-menu'
import { Switch } from '../../components/ui/switch'
import { normalizeContinueUnit } from './logisticsUtils'

function LogisticsListItem({ item, selectedIds, togglingIds, onToggleSelect, onEdit, onDelete, onToggleActive, onToggleTransport }) {
  const isOverflowDisabled = item.disabled_by_overflow === 1
  const cardClass = !item.is_active
    ? 'opacity-60 grayscale-[30%]'
    : isOverflowDisabled
      ? 'opacity-50 text-text-muted'
      : ''
  return (
    <Card
      className={`bg-surface-container border-surface-high transition-all hover:shadow-sm hover:border-surface-highest ${cardClass}`}
      title={isOverflowDisabled ? '套餐变更已暂停，请在 48 小时窗口内重新选择' : undefined}
    >
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-[auto_2fr_1fr_1fr_1fr_1fr_0.5fr_0.5fr_auto] gap-x-6 gap-y-4 items-center">
            <div className="flex items-center">
              <Checkbox checked={selectedIds.has(item.id)} onCheckedChange={() => onToggleSelect(item.id)} />
            </div>
            <div className="font-medium flex flex-wrap gap-2 items-center min-w-0">
              <span className="truncate" title={item.name}>{item.name}</span>
              {item.is_smart === 1 && (
                <Badge className="bg-status-success/15 text-status-success hover:bg-status-success/25 border-transparent text-[10px] px-1.5 py-0 h-4 transition-colors">Smart</Badge>
              )}
              {isOverflowDisabled && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-status-warning/40 text-status-warning">已暂停</Badge>
              )}
            </div>
            <div>
              <Badge variant="outline" className="text-xs">
                {item.delivery_method === 'pickup' ? '取货点' : item.delivery_method === 'door' ? '送货上门' : '未知'}
              </Badge>
            </div>
            <div className="text-sm text-text-secondary">{item.min_days || 0}-{item.max_days || 0}天</div>
            <div className="text-sm">{item.base_fee != null ? `¥${Number(item.base_fee).toFixed(2)}` : '-'}</div>
            <div className="text-sm">
              {item.continue_fee != null ? `¥${Number(item.continue_fee).toFixed(5)}/${normalizeContinueUnit(item.continue_unit)}` : '-'}
            </div>
            <div className="flex items-center gap-1">
              {item.allow_battery ? <Zap className="h-4 w-4 text-status-success" /> : <Zap className="h-4 w-4 text-surface-highest" />}
            </div>
            <div className="flex items-center gap-1">
              {item.allow_liquid ? <Droplets className="h-4 w-4 text-status-info" /> : <Droplets className="h-4 w-4 text-surface-highest" />}
            </div>
            <div className="flex items-center gap-2 justify-end">
              <Switch
                checked={!!item.is_active}
                disabled={togglingIds.has(item.id)}
                onCheckedChange={(checked) => onToggleActive(item.id, checked)}
              />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="操作菜单">
                    <MoreHorizontal className="h-4 w-4 text-text-secondary" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-36">
                  <DropdownMenuItem onClick={() => onEdit(item)} className="cursor-pointer" aria-label="编辑">
                    <Pencil className="h-4 w-4 mr-2 text-text-muted" />
                    编辑
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="cursor-pointer"
                    aria-label={item.type === 'land' ? '转空运' : '转陆运'}
                    onClick={() => onToggleTransport(item.id, item.type)}
                  >
                    <ArrowLeftRight className="h-4 w-4 mr-2 text-text-muted" />
                    {item.type === 'land' ? '转空运' : '转陆运'}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="cursor-pointer text-status-error focus:text-status-error focus:bg-status-error/10"
                    aria-label="删除"
                    onClick={() => onDelete(item.id)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function LogisticsList(props) {
  const { items } = props

  return (
    <div className="space-y-2">
      {items.length === 0 ? (
        <div className="text-center text-text-muted py-8">暂无物流规则</div>
      ) : (
        items.map((item) => <LogisticsListItem key={item.id} item={item} {...props} />)
      )}
    </div>
  )
}
