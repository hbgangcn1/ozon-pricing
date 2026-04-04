import React from 'react';
import { cn } from '@/lib/utils';

const Progress = React.forwardRef(({ className, value, max = 100, ...props }, ref) => {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
  
  return (
    <div
      ref={ref}
      className={cn(
        'relative h-2 w-full overflow-hidden rounded-full bg-zinc-800',
        className
      )}
      {...props}
    >
      <div
        className="h-full bg-blue-500 transition-all"
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
});

Progress.displayName = 'Progress';

export { Progress };