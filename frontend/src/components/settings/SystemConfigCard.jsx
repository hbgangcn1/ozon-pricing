import React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "../ui/card"
import { Settings } from "lucide-react"
import { Label } from "../ui/label"
import { Switch } from "../ui/switch"

const SystemConfigCard = ({ config, setConfig, saving, handleSaveConfig }) => {
  return (
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
              checked={config?.openRegistration || false}
              disabled={saving}
              onCheckedChange={(val) => {
                if (setConfig) setConfig({ ...config, openRegistration: val })
                handleSaveConfig(val)
              }}
            />
            <span className="text-sm text-text-secondary">
              {saving ? "更新中..." : (config?.openRegistration ? "已开启" : "已关闭")}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default SystemConfigCard
