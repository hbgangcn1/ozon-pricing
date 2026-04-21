import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DraftRestoreDialog from '../components/DraftRestoreDialog'

const alertDialogContentProps = {
  current: null,
}

vi.mock('../components/ui/alert-dialog', () => ({
  AlertDialog: ({ children, open }) => (open ? <div data-testid="draft-alert-dialog">{children}</div> : null),
  AlertDialogContent: ({ children, ...props }) => {
    alertDialogContentProps.current = props
    return <div data-testid="draft-alert-dialog-content">{children}</div>
  },
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <h2>{children}</h2>,
  AlertDialogDescription: ({ children }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, onClick, className }) => (
    <button type="button" onClick={onClick} className={className}>
      {children}
    </button>
  ),
}))

describe('DraftRestoreDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    alertDialogContentProps.current = null
  })

  it('renders title, description and optional summary', () => {
    render(
      <DraftRestoreDialog
        open
        onRestore={vi.fn()}
        onDiscard={vi.fn()}
        summary="包含 9 个字段"
      />,
    )

    expect(screen.getByText('检测到未完成的填写')).toBeInTheDocument()
    expect(screen.getByText('上次会话过期前，您正在填写本页表单。是否恢复内容？')).toBeInTheDocument()
    expect(screen.getByText('包含 9 个字段')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '恢复' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '丢弃' })).toBeInTheDocument()
  })

  it('calls the correct button callbacks', () => {
    const onRestore = vi.fn()
    const onDiscard = vi.fn()

    render(
      <DraftRestoreDialog
        open
        onRestore={onRestore}
        onDiscard={onDiscard}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '恢复' }))
    fireEvent.click(screen.getByRole('button', { name: '丢弃' }))

    expect(onRestore).toHaveBeenCalledTimes(1)
    expect(onDiscard).toHaveBeenCalledTimes(1)
  })

  it('prevents escape key and outside pointer close', () => {
    render(
      <DraftRestoreDialog
        open
        onRestore={vi.fn()}
        onDiscard={vi.fn()}
      />,
    )

    const escapeEvent = { preventDefault: vi.fn() }
    const outsideEvent = { preventDefault: vi.fn() }

    alertDialogContentProps.current.onEscapeKeyDown(escapeEvent)
    alertDialogContentProps.current.onPointerDownOutside(outsideEvent)

    expect(escapeEvent.preventDefault).toHaveBeenCalledTimes(1)
    expect(outsideEvent.preventDefault).toHaveBeenCalledTimes(1)
  })
})
