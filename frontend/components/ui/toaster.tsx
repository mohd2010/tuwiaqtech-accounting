"use client";

import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";
import {
  ToastContext,
  useToast,
  useToastState,
} from "@/hooks/useToast";

/**
 * Provides the shared toast context to children and renders all active toasts.
 * Mount once near the root of the component tree (e.g. in layout.tsx),
 * wrapping the page content so any descendant can call `useToast()`.
 */
export function Toaster({ children }: { children: React.ReactNode }) {
  const state = useToastState();

  return (
    <ToastContext.Provider value={state}>
      {children}
      <ToastRenderer />
    </ToastContext.Provider>
  );
}

function ToastRenderer() {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <ToastProvider>
      {toasts.map((t) => (
        <Toast
          key={t.id}
          variant={t.variant}
          open
          onOpenChange={(open) => {
            if (!open) dismiss(t.id);
          }}
        >
          <div className="grid gap-1">
            <ToastTitle>{t.title}</ToastTitle>
            {t.description && (
              <ToastDescription>{t.description}</ToastDescription>
            )}
          </div>
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}
