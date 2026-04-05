import React from "react"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "../ui/alert-dialog"
import { AlertTriangle, Loader2 } from "lucide-react"

const RestoreBackupDialog = ({ open, onOpenChange, onConfirm, selectedBackup, loading }) => {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>⚠️ 确认恢复</AlertDialogTitle>
          <AlertDialogDescription>
            <div className="space-y-2 mt-2">
              <p>
                确定要从备份 <strong>{selectedBackup}</strong> 恢复数据库吗？
              </p>
              <div className="bg-status-warning/10 border border-status-warning/20 rounded p-3 text-sm">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-status-warning mt-0.5 shrink-0" />
                  <div>
                    <p className="text-status-warning font-medium">恢复前会自动创建快照</p>
                    <p className="text-text-secondary mt-1">
                      pre_restore 快照会在恢复前自动创建，如恢复后有问题可从这里回滚。
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-text-secondary">此操作将覆盖当前所有数据，确定要继续吗？</p>
              <p className="text-text-secondary">⚠️ 恢复后需要重新登录。</p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>取消</AlertDialogCancel>
          <AlertDialogAction className="bg-status-success hover:bg-status-success/85" disabled={loading} onClick={onConfirm}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                恢复中...
              </>
            ) : "确认恢复"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default RestoreBackupDialog
