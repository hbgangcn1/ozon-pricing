import { useCallback, useEffect, useMemo, useState } from 'react'
import { Trash2, Download, PlayCircle } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../components/ui/button'
import { settingsAPI, logoutUser } from '../services/api'
import SystemConfigCard from '../components/settings/SystemConfigCard'
import BackupManagementCard from '../components/settings/BackupManagementCard'
import FAQSection from '../components/settings/FAQSection'
import DeleteAccountDialog from '../components/settings/DeleteAccountDialog'
import RestoreBackupDialog from '../components/settings/RestoreBackupDialog'


function SettingsPage() {
  // 系统设置
  const [openRegistration, setOpenRegistration] = useState(true)
  const [registrationLoading, setRegistrationLoading] = useState(false)

  // 备份列表
  const [backups, setBackups] = useState([])
  const [backupsLoading, setBackupsLoading] = useState(false)
  const [backupInProgress, setBackupInProgress] = useState(false)
  const [restoreInProgress, setRestoreInProgress] = useState(false)

  // 备份设置
  const [backupSettings, setBackupSettings] = useState({ enabled: true, interval_hours: 6, max_backups: 28, next_backup: null })
  const [settingsLoading, setSettingsLoading] = useState(false)

  // 备份统计
  const [backupStats, setBackupStats] = useState({ count: 0, total_size_mb: 0 })

  // FAQ 折叠
  const [_expandedFaq, _setExpandedFaq] = useState(null)

  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState(null) // { name }

  // 恢复确认
  const [restoreTarget, setRestoreTarget] = useState(null) // { name }

  // ---------------------------------------------------------------------------
  // 数据加载
  // ---------------------------------------------------------------------------
  const loadBackups = useCallback(async (signal) => {
    const backupsData = await settingsAPI.getBackups()
    if (!signal?.aborted) {
      setBackups(backupsData)
    }
    return backupsData
  }, [])

  const loadBackupSettings = useCallback(async (signal) => {
    const settingsData = await settingsAPI.getBackupSettings()
    if (!signal?.aborted) {
      setBackupSettings(settingsData)
    }
    return settingsData
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    const loadAll = async () => {
      setBackupsLoading(true)
      setSettingsLoading(true)
      try {
        const [, , statsData, systemData] = await Promise.all([
          loadBackups(controller.signal),
          loadBackupSettings(controller.signal),
          settingsAPI.getBackupStats(),
          settingsAPI.get(),
        ])

        if (!controller.signal.aborted) {
          setBackupStats(statsData)
          setOpenRegistration(systemData.open_registration)
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          toast.error('加载系统设置失败')
        }
      } finally {
        if (!controller.signal.aborted) {
          setBackupsLoading(false)
          setSettingsLoading(false)
        }
      }
    }

    loadAll()
    return () => controller.abort()
  }, [loadBackups, loadBackupSettings])

  // ---------------------------------------------------------------------------
  // 手动备份
  // ---------------------------------------------------------------------------
  const handleCreateBackup = async () => {
    setBackupInProgress(true)
    const toastId = toast.loading('🔄 正在备份数据库...', { duration: 999999 })
    try {
      const result = await settingsAPI.createBackup()
      toast.dismiss(toastId)
      toast.success(result.message || '备份成功')
      await loadBackups()
      await loadBackupSettings()
    } catch (e) {
      toast.dismiss(toastId)
      toast.error('备份失败: ' + (e.response?.data?.message || e.message))
    } finally {
      setBackupInProgress(false)
    }
  }

  // ---------------------------------------------------------------------------
  // 下载备份
  // ---------------------------------------------------------------------------
  const handleDownload = async (filename) => {
    try {
      const response = await settingsAPI.downloadBackup(filename)
      const url = window.URL.createObjectURL(new Blob([response]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.parentNode.removeChild(link)
      window.URL.revokeObjectURL(url)
      toast.success(`已下载: ${filename}`)
    } catch (e) {
      toast.error('下载失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  // ---------------------------------------------------------------------------
  // 删除备份
  // ---------------------------------------------------------------------------
  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      const result = await settingsAPI.deleteBackup(deleteTarget.name)
      toast.success(result.message || '已删除')
      setDeleteTarget(null)
      await loadBackups()
      await loadBackupSettings()
    } catch (e) {
      toast.error('删除失败: ' + (e.response?.data?.message || e.message))
    }
  }

  // ---------------------------------------------------------------------------
  // 恢复备份
  // ---------------------------------------------------------------------------
  const handleRestore = async () => {
    if (!restoreTarget) return
    const backupName = restoreTarget.name

    // 关闭确认对话框，立即开始恢复
    setRestoreTarget(null)
    setRestoreInProgress(true)

    // 显示加载提示（持续显示，直到页面跳转）
    toast.loading('🔄 正在恢复数据库，这可能需要十几秒，请稍候...', { id: 'restore-progress', duration: 999999 })

    try {
      await settingsAPI.restoreBackup(backupName, true)
      toast.dismiss('restore-progress')
      toast.success(`✅ 数据库已从「${backupName}」恢复。请重新登录。`, { duration: 8000 })
      // 恢复后数据库被覆盖，当前 token 失效，强制重新登录
      setTimeout(() => logoutUser(), 1500)
    } catch (e) {
      toast.dismiss('restore-progress')
      const msg = e.response?.data?.message || e.message || '恢复失败'
      toast.error('恢复失败: ' + msg)
      setRestoreInProgress(false)
    }
  }

  // ---------------------------------------------------------------------------
  // 更新开放注册
  // ---------------------------------------------------------------------------
  const handleOpenRegistrationChange = async (enabled) => {
    setRegistrationLoading(true)
    try {
      await settingsAPI.updateOpenRegistration(enabled)
      setOpenRegistration(enabled)
      toast.success('设置已更新')
    } catch (e) {
      toast.error('更新失败: ' + (e.response?.data?.message || e.message))
    } finally {
      setRegistrationLoading(false)
    }
  }

  // ---------------------------------------------------------------------------
  // 表格列定义
  // ---------------------------------------------------------------------------
  const backupColumns = useMemo(() => ([
    {
      header: '文件名',
      accessorKey: 'name',
      cell: ({ row }) => (
        <code className="bg-surface-container px-2 py-1 rounded text-sm">{row.original.name}</code>
      ),
    },
    { header: '大小', accessorKey: 'size', width: 100 },
    { header: '备份时间', accessorKey: 'time', width: 160 },
    { header: '类型', accessorKey: 'type', width: 80 },
    {
      header: '操作',
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDownload(row.original.name)}
          >
            <Download className="h-4 w-4 mr-1" />
            下载
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-status-success hover:text-status-success/80 transition-all duration-200"
            onClick={() => setRestoreTarget({ name: row.original.name })}
          >
            <PlayCircle className="h-4 w-4 mr-1" />
            恢复
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-status-error hover:text-status-error/80 transition-all duration-200"
            onClick={() => setDeleteTarget({ name: row.original.name })}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            删除
          </Button>
        </div>
      ),
    },
  ]), [])

  // ---------------------------------------------------------------------------
  // FAQ
  // ---------------------------------------------------------------------------
  const faqItems = useMemo(() => ([
    {
      id: 'backup-format',
      question: '备份文件格式是什么？',
      answer:
        '备份文件格式为 PostgreSQL dump (.dump)，这是 PostgreSQL 的标准导出格式，可以包含完整的数据库结构和数据。',
    },
    {
      id: 'auto-backup',
      question: '自动备份频率是多少？',
      answer:
        `系统当前设置为每 ${backupSettings.interval_hours} 小时自动执行一次备份，保留最近 ${backupSettings.max_backups} 个备份文件。`,
    },
    {
      id: 'backup-naming',
      question: '备份文件命名规则是什么？',
      answer:
        '自动备份: auto_backup_YYYYMMDD_HHMMSS.dump\n手动备份: manual_backup_YYYYMMDD_HHMMSS.dump\n恢复前快照: pre_restore_YYYYMMDD_HHMMSS.dump',
    },
    {
      id: 'restore-backup',
      question: '如何恢复备份？',
      answer:
        '点击备份列表中的"恢复"按钮，系统会先创建一个 pre_restore 快照，然后执行恢复。\n\n⚠️ 注意：恢复备份将覆盖当前数据库，请谨慎操作。',
    },
    {
      id: 'backup-safety',
      question: '备份安全性如何保障？',
      answer:
        '所有备份文件存储在本地安全目录，仅管理员可访问。恢复操作前会自动创建快照，可在恢复后用于回滚。',
    },
  ]), [backupSettings.interval_hours, backupSettings.max_backups])

  return (
    <div className="bg-surface min-h-screen p-6">
      {/* 删除确认 */}
      <DeleteAccountDialog 
        open={!!deleteTarget} 
        onOpenChange={(o) => !o && setDeleteTarget(null)} 
        onConfirm={handleDelete} 
        loading={false} 
        targetName={deleteTarget?.name} 
      />

      {/* 恢复确认 */}
      <RestoreBackupDialog 
        open={!!restoreTarget} 
        onOpenChange={(o) => !restoreInProgress && o && setRestoreTarget(null)} 
        onConfirm={handleRestore} 
        selectedBackup={restoreTarget?.name} 
        loading={restoreInProgress} 
      />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary mb-2 font-headline tracking-tight">⚙️ 系统设置</h1>
        <p className="text-text-secondary">配置系统参数、备份管理和系统信息</p>
      </div>

      {/* 系统配置 */}
      <SystemConfigCard 
        config={{ openRegistration }} 
        setConfig={null} 
        saving={registrationLoading} 
        handleSaveConfig={handleOpenRegistrationChange} 
      />

      {/* 数据库备份管理 */}
      <BackupManagementCard 
        backupStats={backupStats}
        backupInProgress={backupInProgress}
        handleCreateBackup={handleCreateBackup}
        backupsLoading={backupsLoading}
        backups={backups}
        backupColumns={backupColumns}
        settingsLoading={settingsLoading}
        backupSettings={backupSettings}
      />

      {/* FAQ */}
      <FAQSection faqItems={faqItems} />
    </div>
  )
}

export default SettingsPage
