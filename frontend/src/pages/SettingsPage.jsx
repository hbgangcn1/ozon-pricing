import { useState, useEffect, useCallback } from 'react'
import {
  Download, RefreshCw, Settings, FolderOpen, Info, ChevronDown,
  Clock, HardDrive, Database, Trash2, PlayCircle, Loader2, AlertTriangle
} from 'lucide-react'
import { toast } from 'sonner'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Badge } from '../components/ui/badge'
import { Switch } from '../components/ui/switch'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog'
import { settingsAPI, logoutUser } from '../services/api'

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
  const [expandedFaq, setExpandedFaq] = useState(null)

  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState(null) // { name }

  // 恢复确认
  const [restoreTarget, setRestoreTarget] = useState(null) // { name }

  // ---------------------------------------------------------------------------
  // 数据加载
  // ---------------------------------------------------------------------------
  const loadBackups = useCallback(async () => {
    setBackupsLoading(true)
    try {
      const data = await settingsAPI.getBackups()
      setBackups(data)
    } catch (e) {
      console.error('加载备份列表失败', e)
      toast.error('加载备份列表失败')
    } finally {
      setBackupsLoading(false)
    }
  }, [])

  const loadBackupSettings = useCallback(async () => {
    setSettingsLoading(true)
    try {
      const [settings, stats] = await Promise.all([
        settingsAPI.getBackupSettings(),
        settingsAPI.getBackupStats(),
      ])
      setBackupSettings(settings)
      setBackupStats(stats)
    } catch (e) {
      console.error('加载备份设置失败', e)
      toast.error('加载备份设置失败')
    } finally {
      setSettingsLoading(false)
    }
  }, [])

  const loadSystemSettings = useCallback(async () => {
    try {
      const data = await settingsAPI.get()
      setOpenRegistration(data.open_registration)
    } catch (e) {
      console.error('加载系统设置失败', e)
    }
  }, [])

  useEffect(() => {
    loadBackups()
    loadBackupSettings()
    loadSystemSettings()
  }, [loadBackups, loadBackupSettings, loadSystemSettings])

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
      const result = await settingsAPI.restoreBackup(backupName, true)
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
  const backupColumns = [
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
            className="text-green-400 hover:text-green-300"
            onClick={() => setRestoreTarget({ name: row.original.name })}
          >
            <PlayCircle className="h-4 w-4 mr-1" />
            恢复
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-red-400 hover:text-red-300"
            onClick={() => setDeleteTarget({ name: row.original.name })}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            删除
          </Button>
        </div>
      ),
    },
  ]

  // ---------------------------------------------------------------------------
  // FAQ
  // ---------------------------------------------------------------------------
  const faqItems = [
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
  ]

  return (
    <div className="bg-surface min-h-screen p-6">
      {/* 删除确认 */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除备份文件 <strong>{deleteTarget?.name}</strong> 吗？此操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 恢复确认 */}
      <AlertDialog open={!!restoreTarget} onOpenChange={(o) => !restoreInProgress && o && setRestoreTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>⚠️ 确认恢复</AlertDialogTitle>
            <AlertDialogDescription>
              <div className="space-y-2 mt-2">
                <p>
                  确定要从备份 <strong>{restoreTarget?.name}</strong> 恢复数据库吗？
                </p>
                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded p-3 text-sm">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-400 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-yellow-400 font-medium">恢复前会自动创建快照</p>
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
            <AlertDialogCancel disabled={restoreInProgress}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-green-600 hover:bg-green-700"
              disabled={restoreInProgress}
              onClick={handleRestore}
            >
              {restoreInProgress ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  恢复中...
                </>
              ) : '确认恢复'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary mb-2">⚙️ 系统设置</h1>
        <p className="text-text-secondary">配置系统参数、备份管理和系统信息</p>
      </div>

      {/* 系统配置 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            系统配置
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 bg-surface-container/50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="flex flex-col">
                <Label className="text-text-primary">开放注册</Label>
                <p className="text-sm text-text-secondary">开启后，新用户可以自行注册账号</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={openRegistration}
                disabled={registrationLoading}
                onCheckedChange={handleOpenRegistrationChange}
              />
              <span className="text-sm text-text-secondary">
                {registrationLoading ? '更新中...' : openRegistration ? '已开启' : '已关闭'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 数据库备份管理 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            数据库备份管理
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="list" className="w-full">
            <TabsList className="grid w-full grid-cols-3 bg-surface-container">
              <TabsTrigger value="list" className="data-[state=active]:bg-surface-high">
                📋 备份列表
              </TabsTrigger>
              <TabsTrigger value="auto" className="data-[state=active]:bg-surface-high">
                ⚙️ 自动备份设置
              </TabsTrigger>
              <TabsTrigger value="info" className="data-[state=active]:bg-surface-high">
                ℹ️ 备份说明
              </TabsTrigger>
            </TabsList>

            {/* 备份列表 */}
            <TabsContent value="list" className="mt-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Button
                    onClick={handleCreateBackup}
                    disabled={backupInProgress}
                  >
                    {backupInProgress ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-2" />
                    )}
                    {backupInProgress ? '备份中...' : '🔄 立即备份'}
                  </Button>
                  <p className="text-text-secondary">
                    共有 <span className="text-text-primary font-medium">{backupStats.count}</span> 个备份，
                    总计 <span className="text-text-primary font-medium">{backupStats.total_size_mb} MB</span>
                  </p>
                </div>

                {backupsLoading ? (
                  <div className="flex items-center justify-center py-12 text-text-secondary">
                    <Loader2 className="h-6 w-6 mr-2 animate-spin" />
                    加载中...
                  </div>
                ) : backups.length === 0 ? (
                  <div className="text-center py-12 text-text-secondary">
                    暂无备份文件
                  </div>
                ) : (
                  <div className="border border-surface-high rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-surface-high hover:bg-transparent">
                          {backupColumns.map((column) => (
                            <TableHead
                              key={column.header}
                              className="text-text-secondary bg-surface-container/50"
                              style={column.width ? { width: column.width } : undefined}
                            >
                              {column.header}
                            </TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {backups.map((backup) => (
                          <TableRow
                            key={backup.name}
                            className="border-surface-high hover:bg-surface-container/50"
                          >
                            {backupColumns.map((column) => (
                              <TableCell key={column.header} className="text-text-primary">
                                {column.cell
                                  ? column.cell({ row: { original: backup } })
                                  : backup[column.accessorKey]}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </TabsContent>

            {/* 自动备份设置 */}
            <TabsContent value="auto" className="mt-4">
              {settingsLoading ? (
                <div className="flex items-center justify-center py-12 text-text-secondary">
                  <Loader2 className="h-6 w-6 mr-2 animate-spin" />
                  加载中...
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 bg-surface-container/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="h-4 w-4 text-text-secondary" />
                        <span className="text-text-secondary">自动备份</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={backupSettings.enabled}
                          disabled
                        />
                        <span className="text-text-primary">
                          {backupSettings.enabled ? '已开启' : '已关闭'}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 bg-surface-container/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="h-4 w-4 text-text-secondary" />
                        <span className="text-text-secondary">备份频率</span>
                      </div>
                      <p className="text-text-primary">每 {backupSettings.interval_hours} 小时</p>
                    </div>

                    <div className="p-4 bg-surface-container/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Database className="h-4 w-4 text-text-secondary" />
                        <span className="text-text-secondary">保留数量</span>
                      </div>
                      <p className="text-text-primary">保留最近 {backupSettings.max_backups} 个</p>
                    </div>

                    <div className="p-4 bg-surface-container/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="h-4 w-4 text-text-secondary" />
                        <span className="text-text-secondary">下次备份时间</span>
                      </div>
                      <p className="text-text-primary">
                        {backupSettings.next_backup || '未知'}
                      </p>
                    </div>

                    <div className="p-4 bg-surface-container/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <FolderOpen className="h-4 w-4 text-text-secondary" />
                        <span className="text-text-secondary">备份存储位置</span>
                      </div>
                      <p className="text-text-primary font-mono text-sm">
                        {backupSettings.backup_path || '服务器本地备份目录'}
                      </p>
                    </div>

                    <div className="p-4 bg-surface-container/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <HardDrive className="h-4 w-4 text-text-secondary" />
                        <span className="text-text-secondary">备份总大小</span>
                      </div>
                      <p className="text-text-primary">{backupStats.total_size_mb} MB ({backupStats.count} 个)</p>
                    </div>
                  </div>

                  <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                    <div className="flex items-start gap-3">
                      <Info className="h-5 w-5 text-blue-400 mt-0.5 shrink-0" />
                      <div className="text-sm text-text-secondary">
                        自动备份在后台每 {backupSettings.interval_hours} 小时执行一次。手动备份无限制。
                        超过 {backupSettings.max_backups} 个自动备份时，系统会自动删除最旧的备份。
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </TabsContent>

            {/* 备份说明 */}
            <TabsContent value="info" className="mt-4">
              <div className="space-y-4">
                <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-blue-400 mt-0.5 shrink-0" />
                    <div>
                      <h3 className="font-medium text-blue-400 mb-2">备份说明</h3>
                      <ul className="space-y-1 text-text-secondary">
                        <li>• 备份文件格式为 PostgreSQL dump (.dump)</li>
                        <li>• 自动备份频率：每 {backupSettings.interval_hours} 小时一次</li>
                        <li>• 备份文件命名：auto_backup_YYYYMMDD_HHMMSS.dump / manual_backup_...</li>
                        <li>• 恢复备份将覆盖当前数据库，请谨慎操作</li>
                        <li>• 恢复前会自动创建 pre_restore 快照</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <h3 className="font-medium text-text-primary">如何恢复备份？</h3>
                  <ol className="list-decimal list-inside space-y-2 text-text-secondary">
                    <li>在备份列表中找到要恢复的备份</li>
                    <li>点击"恢复"按钮</li>
                    <li>系统自动创建 pre_restore 快照</li>
                    <li>数据恢复到所选备份的时间点</li>
                    <li>完成后显示恢复结果</li>
                  </ol>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* FAQ */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            常见问题 (FAQ)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {faqItems.map((item) => (
              <div key={item.id} className="border border-surface-high rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedFaq(expandedFaq === item.id ? null : item.id)}
                  className="w-full flex items-center justify-between p-4 bg-surface-container/50 hover:bg-surface-high transition-colors"
                >
                  <span className="text-text-primary font-medium">{item.question}</span>
                  {expandedFaq === item.id ? (
                    <ChevronDown className="h-4 w-4 text-text-secondary shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-text-secondary shrink-0" />
                  )}
                </button>
                {expandedFaq === item.id && (
                  <div className="p-4 bg-surface/50 text-text-secondary whitespace-pre-line">
                    {item.answer}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default SettingsPage
