import React from 'react'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'

export default function RateInput({ label, value, onChange, defaultVal, step }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        type="number"
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={defaultVal}
        className="h-8"
      />
    </div>
  )
}
