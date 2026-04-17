import React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "../ui/card"
import { HardDrive, RefreshCw, Loader2, Clock, Database, FolderOpen, Info } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs"
import { Button } from "../ui/button"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../ui/table"
import { Switch } from "../ui/switch"

const BackupManagementCard = ({
  backupStats,
  backupInProgress,
  handleCreateBackup,
  backupsLoading,
  backups,
  backupColumns,
  settingsLoading,
  backupSettings
}) => {
  return (
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
            <TabsTrigger value="list" className="data-[state=active]:bg-surface-high">📋 备份列表</TabsTrigger>
            <TabsTrigger value="auto" className="data-[state=active]:bg-surface-high">⚙️ 自动备份设置</TabsTrigger>
            <TabsTrigger value="info" className="data-[state=active]:bg-surface-high">ℹ️ 备份说明</TabsTrigger>
          </TabsList>

          <TabsContent value="list" className="mt-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Button onClick={handleCreateBackup} disabled={backupInProgress}>
                  {backupInProgress ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                  {backupInProgress ? "备份中..." : "🔄 立即备份"}
                </Button>
                <p className="text-text-secondary">
                  共有 <span className="text-text-primary font-medium">{backupStats?.count || 0}</span> 个备份，
                  总计 <span className="text-text-primary font-medium">{backupStats?.total_size_mb || 0} MB</span>
                </p>
              </div>
              {backupsLoading ? (
                <div className="flex items-center justify-center py-12 text-text-secondary">
                  <Loader2 className="h-6 w-6 mr-2 animate-spin" /> 加载中...
                </div>
              ) : backups?.length === 0 ? (
                <div className="text-center py-12 text-text-secondary">暂无备份文件</div>
              ) : (
                <div className="border border-surface-high rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-surface-high hover:bg-transparent">
                        {backupColumns.map((column) => (
                          <TableHead key={column.header} className="text-text-secondary bg-surface-container/50" style={column.width ? { width: column.width } : undefined}>
                            {column.header}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {backups.map((backup) => (
                        <TableRow key={backup.name} className="border-surface-high hover:bg-surface-container/50">
                          {backupColumns.map((column) => (
                            <TableCell key={column.header} className="text-text-primary">
                              {column.cell ? column.cell({ row: { original: backup } }) : backup[column.accessorKey]}
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

          <TabsContent value="auto" className="mt-4">
            {settingsLoading ? (
              <div className="flex items-center justify-center py-12 text-text-secondary">
                <Loader2 className="h-6 w-6 mr-2 animate-spin" /> 加载中...
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
                      <Switch checked={backupSettings?.enabled || false} disabled />
                      <span className="text-text-primary">{backupSettings?.enabled ? "已开启" : "已关闭"}</span>
                    </div>
                  </div>
                  <div className="p-4 bg-surface-container/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="h-4 w-4 text-text-secondary" />
                      <span className="text-text-secondary">备份频率</span>
                    </div>
                    <p className="text-text-primary">每 {backupSettings?.interval_hours || 6} 小时</p>
                  </div>
                  <div className="p-4 bg-surface-container/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Database className="h-4 w-4 text-text-secondary" />
                      <span className="text-text-secondary">保留数量</span>
                    </div>
                    <p className="text-text-primary">保留最近 {backupSettings?.max_backups || 28} 个</p>
                  </div>
                  <div className="p-4 bg-surface-container/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="h-4 w-4 text-text-secondary" />
                      <span className="text-text-secondary">下次备份时间</span>
                    </div>
                    <p className="text-text-primary">{backupSettings?.next_backup || "未知"}</p>
                  </div>
                  <div className="p-4 bg-surface-container/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <FolderOpen className="h-4 w-4 text-text-secondary" />
                      <span className="text-text-secondary">备份存储位置</span>
                    </div>
                    <p className="text-text-primary font-mono text-sm">{backupSettings?.backup_path || "服务器本地备份目录"}</p>
                  </div>
                  <div className="p-4 bg-surface-container/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <HardDrive className="h-4 w-4 text-text-secondary" />
                      <span className="text-text-secondary">备份总大小</span>
                    </div>
                    <p className="text-text-primary">{backupStats?.total_size_mb || 0} MB ({backupStats?.count || 0} 个)</p>
                  </div>
                </div>
                <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-primary-dim mt-0.5 shrink-0" />
                    <div className="text-sm text-text-secondary">
                      自动备份在后台每 {backupSettings?.interval_hours || 6} 小时执行一次。手动备份无限制。超过 {backupSettings?.max_backups || 28} 个自动备份时，系统会自动删除最旧的备份。
                    </div>
                  </div>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="info" className="mt-4">
            <div className="space-y-4">
              <div className="p-4 bg-primary/10 border border-primary/20 rounded-lg">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-primary-dim mt-0.5 shrink-0" />
                  <div>
                    <h3 className="font-medium text-primary-dim mb-2 font-headline tracking-tight">备份说明</h3>
                    <ul className="space-y-1 text-text-secondary">
                      <li>• 备份文件格式为 PostgreSQL dump (.dump)</li>
                      <li>• 自动备份频率：每 {backupSettings?.interval_hours || 6} 小时一次</li>
                      <li>• 备份文件命名：auto_backup_YYYYMMDD_HHMMSS.dump / manual_backup_...</li>
                      <li>• 恢复备份将覆盖当前数据库，请谨慎操作</li>
                      <li>• 恢复前会自动创建 pre_restore 快照</li>
                    </ul>
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                <h3 className="font-medium text-text-primary font-headline tracking-tight">如何恢复备份？</h3>
                <ol className="list-decimal list-inside space-y-2 text-text-secondary">
                  <li>在备份列表中找到要恢复的备份</li>
                   <li>点击&quot;恢复&quot;按钮</li>
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
  )
}

export default BackupManagementCard
