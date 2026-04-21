import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SessionKickedDialog from '../components/SessionKickedDialog'

const reasonCases = [
  ['kicked_by_new_login', '账号在其他设备登录', '您的账号刚刚在其他设备登录，本设备会话已结束'],
  ['kicked_by_max_concurrent', '达到最大并发会话数', '您的会话因超出最大并发数被结束'],
  ['password_reset', '密码已重置', '您的密码已被重置，请使用新密码重新登录'],
  ['manual_logout', '您已退出登录', '您的会话已结束'],
]

describe('SessionKickedDialog', () => {
  it.each(reasonCases)('renders correct copy for %s', (reason, title, description) => {
    render(<SessionKickedDialog open reason={reason} onConfirm={vi.fn()} />)

    expect(screen.getByText(title)).toBeInTheDocument()
    expect(screen.getByText(description)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新登录' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '取消' })).not.toBeInTheDocument()
  })

  it('renders fallback copy when reason is null', () => {
    render(<SessionKickedDialog open reason={null} onConfirm={vi.fn()} />)

    expect(screen.getByText('会话已失效')).toBeInTheDocument()
    expect(screen.getByText('您的登录状态已失效，请重新登录')).toBeInTheDocument()
  })

  it('calls onConfirm when clicking relogin button', () => {
    const onConfirm = vi.fn()
    render(<SessionKickedDialog open reason="password_reset" onConfirm={onConfirm} />)

    fireEvent.click(screen.getByRole('button', { name: '重新登录' }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('stays open after escape key and outside clicks', () => {
    render(<SessionKickedDialog open reason="kicked_by_new_login" onConfirm={vi.fn()} />)

    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' })
    fireEvent.pointerDown(document.body)
    fireEvent.mouseDown(document.body)
    fireEvent.click(document.body)

    expect(screen.getByText('账号在其他设备登录')).toBeInTheDocument()
    expect(screen.getByText('您的账号刚刚在其他设备登录，本设备会话已结束')).toBeInTheDocument()
  })
})
