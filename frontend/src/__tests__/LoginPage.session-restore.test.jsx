import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from '../pages/LoginPage'
import { authAPI } from '../services/api'
import { toast } from 'sonner'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../services/api', () => ({
  authAPI: {
    login: vi.fn(),
  },
  settingsAPI: {
    get: vi.fn().mockResolvedValue({ open_registration: true }),
  },
}))

const mockSetAuth = vi.fn()
vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    setAuth: mockSetAuth,
  }),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

describe('LoginPage session restore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderPage(initialEntry) {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <LoginPage />
      </MemoryRouter>,
    )
  }

  it('shows expired session prompt card and info toast', async () => {
    renderPage('/login?returnTo=%2Fpricing%3Ftab%3Dprecise&reason=expired')

    expect(screen.getByText('您的会话已过期，登录后将恢复您的填写内容')).toBeInTheDocument()
    await waitFor(() => {
      expect(toast.info).toHaveBeenCalledWith('您的会话已过期，登录后将恢复您的填写内容')
    })
  })

  it('navigates to relative returnTo after successful login', async () => {
    authAPI.login.mockResolvedValueOnce({
      access_token: 'token',
      user: { id: 1, username: 'alice' },
    })

    renderPage('/login?returnTo=%2Fpricing%3Ftab%3Dprecise&reason=expired')

    fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'ValidPassword123!' } })
    fireEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(mockSetAuth).toHaveBeenCalledWith({ id: 1, username: 'alice' }, 'token')
      expect(mockNavigate).toHaveBeenCalledWith('/pricing?tab=precise')
    })
  })

  it('rejects absolute returnTo values and falls back to root', async () => {
    authAPI.login.mockResolvedValueOnce({
      access_token: 'token',
      user: { id: 1, username: 'alice' },
    })

    renderPage('/login?returnTo=https%3A%2F%2Fevil.example&reason=expired')

    fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'ValidPassword123!' } })
    fireEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })
})
