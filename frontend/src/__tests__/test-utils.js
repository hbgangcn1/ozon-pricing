import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

export const renderWithRouter = (ui, { route = '/' } = {}) => {
  window.history.pushState({}, 'Test page', route)
  return render(ui, { wrapper: MemoryRouter })
}

export const mockUser = (overrides = {}) => ({
  id: 1,
  username: 'testuser',
  role: 'user',
  ...overrides,
})

export const mockProduct = (overrides = {}) => ({
  id: 1,
  name: 'Test Product',
  price: 100,
  ...overrides,
})

export const mockLogisticsItem = (overrides = {}) => ({
  id: 1,
  provider: 'Test Provider',
  cost: 50,
  ...overrides,
})
