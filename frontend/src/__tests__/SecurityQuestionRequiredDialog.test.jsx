import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest'
import { SecurityQuestionRequiredDialog } from '../components/SecurityQuestionRequiredDialog'
import { useAuthStore } from '../stores/authStore'
import { authAPI } from '../services/api'
import { toast } from 'sonner'

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn()
}))

vi.mock('../services/api', () => ({
  authAPI: {
    getSecurityQuestions: vi.fn(),
    setSecurityQuestion: vi.fn()
  }
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn()
  }
}))

vi.mock('../components/ui/select', () => ({
  Select: ({ onValueChange, children, disabled, value }) => (
    <div 
      role="combobox" 
      data-disabled={disabled} 
      data-value={value} 
      onClick={() => {
        if (!disabled) onValueChange('您母亲的姓名是？')
      }}
      data-testid="mock-select"
    >
      {children}
    </div>
  ),
  SelectTrigger: ({ children }) => <>{children}</>,
  SelectContent: ({ children }) => <div role="listbox">{children}</div>,
  SelectItem: ({ value, children }) => <div role="option" data-value={value}>{children}</div>,
  SelectValue: ({ placeholder }) => <div data-testid="select-value">{placeholder}</div>
}))

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  }))
})

window.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false
}
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => {}
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => {}
}

const mockQuestions = [
  '您母亲的姓名是？',
  '您父亲的姓名是？',
  '您出生的城市是？',
  '您小学班主任的姓名是？',
  '您最喜欢的宠物名字是？'
]

describe('SecurityQuestionRequiredDialog', () => {
  const mockLogout = vi.fn()
  const mockOnSuccess = vi.fn()
  const mockOnLogout = vi.fn()

  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.mockImplementation((selector) => {
      const state = { logout: mockLogout }
      return selector ? selector(state) : state
    })
    authAPI.getSecurityQuestions.mockResolvedValue(mockQuestions)
    delete window.location
    window.location = { ...originalLocation, assign: vi.fn(), href: '' }
  })

  afterAll(() => {
    window.location = originalLocation
  })

  it('renders title + description + questions in select + answer input + buttons', async () => {
    render(<SecurityQuestionRequiredDialog open={true} onSuccess={mockOnSuccess} />)

    expect(screen.getByText('请设置安全问题')).toBeInTheDocument()
    expect(
      screen.getByText(/为保护账号，需在继续使用前设置一个安全问题/i)
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(authAPI.getSecurityQuestions).toHaveBeenCalled()
    })

    const selectTrigger = screen.getByRole('combobox')
    fireEvent.click(selectTrigger)
    
    const listbox = await screen.findByRole('listbox')
    expect(listbox).toBeInTheDocument()
    
    const answerInput = screen.getByPlaceholderText('请输入答案')
    expect(answerInput).toBeInTheDocument()
    
    const submitBtn = screen.getByRole('button', { name: /提交/i })
    const logoutBtn = screen.getByRole('button', { name: /退出登录/i })
    expect(submitBtn).toBeInTheDocument()
    expect(logoutBtn).toBeInTheDocument()
  })

  it('submit success calls onSuccess, toast.success', async () => {
    authAPI.setSecurityQuestion.mockResolvedValueOnce({ success: true })

    render(<SecurityQuestionRequiredDialog open={true} onSuccess={mockOnSuccess} />)

    await waitFor(() => {
      const select = screen.getByRole('combobox')
      if (select.getAttribute('data-disabled') === 'true') throw new Error('Still disabled')
    })

    const selectTrigger = screen.getByRole('combobox')
    fireEvent.click(selectTrigger)

    const answerInput = screen.getByPlaceholderText('请输入答案')
    fireEvent.change(answerInput, { target: { value: 'Jane' } })

    const submitBtn = screen.getByRole('button', { name: /提交/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(authAPI.setSecurityQuestion).toHaveBeenCalledWith('您母亲的姓名是？', 'Jane')
      expect(toast.success).toHaveBeenCalledWith('安全问题设置成功')
      expect(mockOnSuccess).toHaveBeenCalled()
    })
  })

  it('logout button triggers authStore.logout (or props.onLogout)', async () => {
    const { rerender } = render(<SecurityQuestionRequiredDialog open={true} onLogout={mockOnLogout} />)
    
    const logoutBtn = screen.getByRole('button', { name: /退出登录/i })
    fireEvent.click(logoutBtn)
    
    expect(mockOnLogout).toHaveBeenCalled()
    
    rerender(<SecurityQuestionRequiredDialog open={true} />)
    fireEvent.click(screen.getByRole('button', { name: /退出登录/i }))
    expect(mockLogout).toHaveBeenCalled()
  })

  it('submit failure shows toast.error', async () => {
    const error = new Error('设置失败')
    error.response = { data: { detail: error.message } }
    authAPI.setSecurityQuestion.mockRejectedValueOnce(error)

    render(<SecurityQuestionRequiredDialog open={true} onSuccess={mockOnSuccess} />)

    await waitFor(() => {
      const select = screen.getByRole('combobox')
      if (select.getAttribute('data-disabled') === 'true') throw new Error('Still disabled')
    })

    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.change(screen.getByPlaceholderText('请输入答案'), { target: { value: 'Jane' } })
    fireEvent.click(screen.getByRole('button', { name: /提交/i }))

    await waitFor(() => {
      expect(authAPI.setSecurityQuestion).toHaveBeenCalledWith('您母亲的姓名是？', 'Jane')
      expect(toast.error).toHaveBeenCalledWith('设置失败')
      expect(mockOnSuccess).not.toHaveBeenCalled()
    })
  })

  it('409 conflict (already set) shows toast.error and closes', async () => {
    authAPI.setSecurityQuestion.mockRejectedValueOnce({
      response: { status: 409, data: { detail: '安全问题已设置' } }
    })

    render(<SecurityQuestionRequiredDialog open={true} onSuccess={mockOnSuccess} />)

    await waitFor(() => {
      const select = screen.getByRole('combobox')
      if (select.getAttribute('data-disabled') === 'true') throw new Error('Still disabled')
    })

    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.change(screen.getByPlaceholderText('请输入答案'), { target: { value: 'Jane' } })
    fireEvent.click(screen.getByRole('button', { name: /提交/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('安全问题已设置，请刷新')
      expect(mockOnSuccess).toHaveBeenCalled()
    })
  })

  it('Dialog cannot close via ESC or outside click', async () => {
    render(<SecurityQuestionRequiredDialog open={true} onSuccess={mockOnSuccess} />)

    await waitFor(() => {
      const select = screen.getByRole('combobox')
      if (select.getAttribute('data-disabled') === 'true') throw new Error('Still disabled')
    })

    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' })
    fireEvent.pointerDown(document.body)

    expect(screen.getByText('请设置安全问题')).toBeInTheDocument()
  })
})
