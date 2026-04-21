import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import PricingResultPanel from '../pages/pricing/PricingResultPanel'

const TabsContext = React.createContext({ value: undefined, setValue: () => {} })

vi.mock('../components/charts/CostPieChart', () => ({
  default: () => <div data-testid="cost-pie-chart" />,
}))

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}))

vi.mock('../components/ui/tabs', () => ({
  Tabs: ({ children, value, onValueChange, defaultValue }) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue)
    const currentValue = value ?? internalValue
    const handleValueChange = onValueChange ?? setInternalValue
    return (
      <TabsContext.Provider value={{ value: currentValue, setValue: handleValueChange }}>
        <div>{children}</div>
      </TabsContext.Provider>
    )
  },
  TabsList: ({ children, className }) => <div className={className}>{children}</div>,
  TabsTrigger: ({ children, value }) => {
    const tabs = React.useContext(TabsContext)
    return <button type="button" onClick={() => tabs.setValue?.(value)}>{children}</button>
  },
  TabsContent: ({ children, value }) => {
    const tabs = React.useContext(TabsContext)
    return tabs.value === value ? <div>{children}</div> : null
  },
}))

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children }) => <span>{children}</span>,
}))

vi.mock('../components/ui/skeleton', () => ({
  Skeleton: ({ className }) => <div className={className} />,
}))

vi.mock('../components/ui/label', () => ({
  Label: ({ children, className, onClick }) => <label className={className} onClick={onClick}>{children}</label>,
}))

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled, 'aria-label': ariaLabel }) => (
    <button type="button" role="switch" aria-label={ariaLabel} aria-checked={checked} disabled={disabled} onClick={() => onCheckedChange?.(!checked)}>
      {checked ? 'on' : 'off'}
    </button>
  ),
}))

vi.mock('../components/ui/collapsible', () => ({
  Collapsible: ({ children }) => <div>{children}</div>,
  CollapsibleTrigger: ({ children, className }) => <button type="button" className={className}>{children}</button>,
  CollapsibleContent: ({ children, className }) => <div className={className}>{children}</div>,
}))

vi.mock('lucide-react', () => ({
  ChevronDown: () => <div data-testid="icon-chevron-down" />,
}))

describe('PricingResultPanel', () => {
  it('renders grouped precise results', () => {
    const groupedResult = {
      rfbs_ru: {
        price_priority: {
          land: {
            is_available: true,
            logistics_name: '俄陆运',
            price_cny: 130,
            profit_margin_pct: 25,
            logistics_cost: 12,
            days_min: 5,
            days_max: 9,
            avg_cost: 14,
            saved_cost: 2,
            avg_days: 7,
            saved_days: 1,
            breakdown: [],
          },
          air: { is_available: false },
        },
        speed_priority: {
          land: { is_available: false },
          air: { is_available: false },
        },
      },
      exchange_rates: { rub_cny: 0.08, usd_cny: 7.2 },
    }

    render(
      <PricingResultPanel
        activeTab="precise"
        fastResult={null}
        preciseResult={{ exchange_rates: { rub_cny: 0.08, usd_cny: 7.2 } }}
        groupedResult={groupedResult}
        groupActiveTab="rfbs_ru"
        setGroupActiveTab={() => {}}
        cisActiveTab="rfbs_KZ"
        setCisActiveTab={() => {}}
        showBreakeven={false}
        setShowBreakeven={() => {}}
      />,
    )

    expect(screen.getByText('分组计算结果')).toBeInTheDocument()
    expect(screen.getByText('俄陆运')).toBeInTheDocument()
    expect(screen.getByText('¥130.00')).toBeInTheDocument()
  })
})
