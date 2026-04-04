import * as React from 'react'
import * as CollapsiblePrimitive from '@radix-ui/react-collapsible'

import { cn } from '../../lib/utils'

const Collapsible = CollapsiblePrimitive.Root

const CollapsibleTrigger = CollapsiblePrimitive.CollapsibleTrigger

const CollapsibleContent = React.forwardRef(
  ({ className, children, ...props }, ref) => (
    <CollapsiblePrimitive.Content
      ref={ref}
      className={cn('overflow-hidden transition-all', className)}
      {...props}
    >
      {children}
    </CollapsiblePrimitive.Content>
  )
)
CollapsibleContent.displayName = CollapsiblePrimitive.Content.displayName

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
