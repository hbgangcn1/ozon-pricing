import { AlertCircle } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog'

const contentByReason = {
  kicked_by_new_login: {
    title: '账号在其他设备登录',
    description: '您的账号刚刚在其他设备登录，本设备会话已结束',
  },
  kicked_by_max_concurrent: {
    title: '达到最大并发会话数',
    description: '您的会话因超出最大并发数被结束',
  },
  password_reset: {
    title: '密码已重置',
    description: '您的密码已被重置，请使用新密码重新登录',
  },
  manual_logout: {
    title: '您已退出登录',
    description: '您的会话已结束',
  },
}

const fallbackContent = {
  title: '会话已失效',
  description: '您的登录状态已失效，请重新登录',
}

function getDialogContent(reason) {
  if (!reason) return fallbackContent
  return contentByReason[reason] || fallbackContent
}

export default function SessionKickedDialog({ open, reason, onConfirm }) {
  const content = getDialogContent(reason)

  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader className="space-y-4 text-left">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-full bg-status-error/10 p-2 text-status-error">
              <AlertCircle className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="space-y-1">
              <AlertDialogTitle>{content.title}</AlertDialogTitle>
              <AlertDialogDescription>{content.description}</AlertDialogDescription>
            </div>
          </div>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction onClick={onConfirm} className="w-full sm:w-auto">
            重新登录
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
