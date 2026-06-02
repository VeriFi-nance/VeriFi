/* eslint-disable react-refresh/only-export-components */
import * as React from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { XIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * ResponsiveDialog: shadcn Dialog above md, bottom sheet below md.
 *
 * Same primitive set as ui/dialog so call sites are interchangeable.
 * Below md (<768px) the content slides up from the bottom with rounded
 * top corners; above md it centers like a normal dialog.
 */

const Root = DialogPrimitive.Root;
const Trigger = DialogPrimitive.Trigger;
const Portal = DialogPrimitive.Portal;
const Close = DialogPrimitive.Close;

function Overlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        'fixed inset-0 z-50 bg-background/10 backdrop-blur-md supports-[backdrop-filter]:bg-background/5 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0',
        className,
      )}
      {...props}
    />
  );
}

function Content({
  className,
  children,
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean;
}) {
  return (
    <Portal>
      <Overlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          'fixed z-50 bg-background outline-none duration-200',
          // Mobile: bottom sheet
          'inset-x-0 bottom-0 max-h-[92dvh] rounded-t-2xl border-t border-x p-5',
          'data-[state=closed]:animate-out data-[state=closed]:slide-out-to-bottom data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom',
          // md+: centered card
          'md:inset-auto md:top-1/2 md:left-1/2 md:bottom-auto md:-translate-x-1/2 md:-translate-y-1/2',
          'md:w-full md:max-w-lg md:rounded-lg md:border md:p-6 md:shadow-lg',
          'md:data-[state=closed]:slide-out-to-bottom-0 md:data-[state=open]:slide-in-from-bottom-0',
          'md:data-[state=closed]:zoom-out-95 md:data-[state=open]:zoom-in-95',
          'flex flex-col gap-4',
          className,
        )}
        {...props}
      >
        {/* Drag handle (mobile only) */}
        <div className="md:hidden mx-auto h-1 w-10 rounded-full bg-muted-foreground/30 -mt-1" aria-hidden />
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            className="absolute top-4 right-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring [&_svg]:size-4"
            aria-label="Close"
          >
            <XIcon />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </Portal>
  );
}

function Header({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-header"
      className={cn('flex flex-col gap-1 text-left', className)}
      {...props}
    />
  );
}

function Footer({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end',
        className,
      )}
      {...props}
    />
  );
}

function Title({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      className={cn('text-lg leading-none font-semibold tracking-tight', className)}
      {...props}
    />
  );
}

function Description({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  );
}

export const ResponsiveDialog = {
  Root,
  Trigger,
  Portal,
  Close,
  Overlay,
  Content,
  Header,
  Footer,
  Title,
  Description,
};

export {
  Root as RDRoot,
  Trigger as RDTrigger,
  Content as RDContent,
  Header as RDHeader,
  Footer as RDFooter,
  Title as RDTitle,
  Description as RDDescription,
  Close as RDClose,
};
