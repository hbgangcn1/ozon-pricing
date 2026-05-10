import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import { useAuthStore } from '../stores/authStore'

vi.mock('../components/Sidebar', () => ({
  default: () => null
}))

vi.mock('../components/TopHeader', () => ({
  default: () => null
}))

vi.mock('../components/SecurityQuestionRequiredDialog', () => ({
  SecurityQuestionRequiredDialog: ({ open }) => <div data-testid="security-dialog-stub" data-open={String(open)} />
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn()
}))

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderLayout = () =>
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<div data-testid="outlet-stub" />} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

  it('does not render SecurityQuestionRequiredDialog when showSecurityDialog is false', () => {
    useAuthStore.mockImplementation((selector) => selector({ showSecurityDialog: false, isAdmin: () => false }))

    renderLayout()

    expect(screen.queryByTestId('security-dialog-stub')).not.toBeInTheDocument()
    expect(screen.getByTestId('outlet-stub')).toBeInTheDocument()
  })

  it('renders SecurityQuestionRequiredDialog when showSecurityDialog is true', () => {
    useAuthStore.mockImplementation((selector) => selector({ showSecurityDialog: true, isAdmin: () => false }))

    renderLayout()

    expect(screen.getByTestId('security-dialog-stub')).toBeInTheDocument()
  })

  it('passes open prop true to dialog when shown', () => {
    useAuthStore.mockImplementation((selector) => selector({ showSecurityDialog: true, isAdmin: () => false }))

    renderLayout()

    expect(screen.getByTestId('security-dialog-stub')).toHaveAttribute('data-open', 'true')
  })
})
