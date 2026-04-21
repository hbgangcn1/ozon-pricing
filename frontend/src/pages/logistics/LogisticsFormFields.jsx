import React, { useEffect, useRef, useState } from 'react'
import { HelpCircle } from 'lucide-react'
import { Label } from '../../components/ui/label'
import { RadioGroupItem } from '../../components/ui/radio-group'

export function SectionTitle({ children }) {
  return (
    <h3 className="text-sm font-semibold text-text-secondary border-b border-surface-high pb-1 mb-3">
      {children}
    </h3>
  )
}

export function FormRow({ children, className = '' }) {
  return <div className={`grid grid-cols-1 sm:grid-cols-2 gap-3 ${className}`}>{children}</div>
}

function TooltipIcon({ content }) {
  const [show, setShow] = useState(false)
  const timeoutRef = useRef(null)

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => setShow(true), 300)
  }

  const handleMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setShow(false)
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (
    <span className="relative inline-flex ml-1">
      <HelpCircle
        className="h-3 w-3 text-text-muted cursor-help"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />
      {show && (
        <span className="absolute left-0 top-full mt-1 z-50 w-64 p-2 text-xs bg-surface-high text-text-primary rounded border border-surface-highest shadow-lg">
          {content}
        </span>
      )}
    </span>
  )
}

export function FormField({ label, tooltip, children }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center">
        <Label className="text-xs text-text-secondary">{label}</Label>
        {tooltip && <TooltipIcon content={tooltip} />}
      </div>
      {children}
    </div>
  )
}

export function RadioLabel({ label, value, itemClassName }) {
  return (
    <div className="flex items-center space-x-2">
      <RadioGroupItem value={value} id={`${value}-${label}`} className={itemClassName} />
      <Label htmlFor={`${value}-${label}`} className="text-sm cursor-pointer">
        {label}
      </Label>
    </div>
  )
}
