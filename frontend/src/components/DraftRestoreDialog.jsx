import React from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog'

export default function DraftRestoreDialog({
  open,
  onRestore,
  onDiscard,
  summary,
}) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent
        onEscapeKeyDown={(event) => event.preventDefault()}
        onPointerDownOutside={(event) => event.preventDefault()}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>检测到未完成的填写</AlertDialogTitle>
          <AlertDialogDescription>
            上次会话过期前，您正在填写本页表单。是否恢复内容？
            {summary ? <span className="mt-2 block text-text-primary">{summary}</span> : null}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={onDiscard}
          >
            丢弃
          </AlertDialogAction>
          <AlertDialogAction onClick={onRestore}>恢复</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
