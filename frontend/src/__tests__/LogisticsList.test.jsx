import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import LogisticsList from '../pages/logistics/LogisticsList'

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}))

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className }) => <span className={className}>{children}</span>,
}))

vi.mock('../components/ui/button', () => ({
  Button: ({ children, ...props }) => <button type="button" {...props}>{children}</button>,
}))

vi.mock('../components/ui/checkbox', () => ({
  Checkbox: ({ checked }) => <input type="checkbox" readOnly checked={checked} />,
}))

vi.mock('../components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children }) => <button type="button">{children}</button>,
}))

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked }) => <input type="checkbox" readOnly checked={checked} />,
}))

vi.mock('lucide-react', () => ({
  ArrowLeftRight: () => <span data-testid="icon-transport" />,
  Droplets: () => <span data-testid="icon-liquid" />,
  MoreHorizontal: () => <span data-testid="icon-more" />,
  Pencil: () => <span data-testid="icon-edit" />,
  Trash2: () => <span data-testid="icon-delete" />,
  Zap: () => <span data-testid="icon-battery" />,
}))

describe('LogisticsList', () => {
  it('renders logistics rows and smart badge', () => {
    render(
      <LogisticsList
        items={[
          {
            id: 1,
            name: '空运FBP-BY',
            type: 'air',
            is_smart: 1,
            is_active: true,
            delivery_method: 'door',
            min_days: 1,
            max_days: 3,
            base_fee: 20,
            continue_fee: 5,
            continue_unit: 'kg',
            allow_battery: true,
            allow_liquid: false,
          },
        ]}
        selectedIds={new Set([1])}
        togglingIds={new Set()}
        onToggleSelect={() => {}}
        onEdit={() => {}}
        onDelete={() => {}}
        onToggleActive={() => {}}
        onToggleTransport={() => {}}
      />,
    )

    expect(screen.getByText('空运FBP-BY')).toBeInTheDocument()
    expect(screen.getByText('Smart')).toBeInTheDocument()
    expect(screen.getByText('送货上门')).toBeInTheDocument()
    expect(screen.getByText('¥20.00')).toBeInTheDocument()
    expect(screen.getByText('¥5.00000/kg')).toBeInTheDocument()
  })
})
