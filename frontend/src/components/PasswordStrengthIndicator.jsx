import React from 'react'
import { Check, X } from 'lucide-react'

const RULES = [
  { key: 'length', label: '至少 13 位', test: (p) => p.length >= 13 },
  { key: 'upper', label: '包含大写字母', test: (p) => /[A-Z]/.test(p) },
  { key: 'lower', label: '包含小写字母', test: (p) => /[a-z]/.test(p) },
  { key: 'digit', label: '包含数字', test: (p) => /\d/.test(p) },
  { key: 'special', label: '包含特殊字符', test: (p) => /[^a-zA-Z0-9]/.test(p) },
]

const STRENGTH_LEVELS = [
  { min: 0, label: '太弱', barClass: 'bg-status-error', textClass: 'text-status-error' },
  { min: 1, label: '弱', barClass: 'bg-status-error', textClass: 'text-status-error' },
  { min: 2, label: '一般', barClass: 'bg-status-warning', textClass: 'text-status-warning' },
  { min: 3, label: '中等', barClass: 'bg-status-warning', textClass: 'text-status-warning' },
  { min: 4, label: '强', barClass: 'bg-primary', textClass: 'text-primary' },
  { min: 5, label: '很强', barClass: 'bg-status-success', textClass: 'text-status-success' },
]

export function evaluatePassword(password) {
  const value = password || ''
  const passed = RULES.filter((r) => r.test(value))
  const score = passed.length
  const level = STRENGTH_LEVELS[score]
  return { score, level, rules: RULES.map((r) => ({ ...r, ok: r.test(value) })) }
}

function PasswordStrengthIndicator({ password }) {
  if (!password) return null
  const { score, level, rules } = evaluatePassword(password)
  const widthPercent = (score / RULES.length) * 100

  return (
    <div className="mt-2 space-y-2" data-testid="password-strength">
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-surface-high rounded-full overflow-hidden">
          <div
            className={`h-full ${level.barClass} transition-all duration-300 ease-out`}
            style={{ width: `${widthPercent}%` }}
            data-testid="password-strength-bar"
          />
        </div>
        <span className={`text-xs font-medium ${level.textClass}`} data-testid="password-strength-label">
          {level.label}
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
        {rules.map((rule) => (
          <li
            key={rule.key}
            className={`flex items-center gap-1.5 text-xs ${rule.ok ? 'text-status-success' : 'text-text-muted'}`}
            data-testid={`password-rule-${rule.key}`}
          >
            {rule.ok ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
            <span>{rule.label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default PasswordStrengthIndicator
