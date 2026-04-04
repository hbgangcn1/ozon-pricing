import React from 'react';
import { cva } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-indigo-500 text-white hover:bg-indigo-600',
        secondary: 'border-transparent bg-zinc-800 text-zinc-50 hover:bg-zinc-700',
        destructive: 'border-transparent bg-red-500 text-white hover:bg-red-600',
        outline: 'border-zinc-700 text-zinc-400 hover:bg-zinc-800',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

function Badge({ className, variant, ...props }) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };