import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface MainContentProps {
  children: ReactNode;
  className?: string;
}

export function MainContent({ children, className }: MainContentProps) {
  return (
    <main className={cn("relative flex-1 w-full flex flex-col min-w-0", className)}>
      <div
        aria-hidden="true"
        className="main-grid-bg pointer-events-none absolute inset-0 z-0"
      />
      <div
        aria-hidden="true"
        className="content-grid-fade pointer-events-none absolute inset-0 z-0"
      />
      
      <div className="relative z-10 w-full px-4 sm:px-6 py-5 pb-24 md:pb-8 flex-1">
        {children}
      </div>
    </main>
  );
}
