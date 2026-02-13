"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";

export type ToastVariant = "default" | "success" | "error" | "warning";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toasts: ToastItem[];
  toast: (opts: {
    title: string;
    description?: string;
    variant?: ToastVariant;
  }) => void;
  dismiss: (id: string) => void;
}

let toastCount = 0;

export const ToastContext = createContext<ToastContextValue | null>(null);

/**
 * Must be used inside a `<ToastContextProvider>`. All callers share the same
 * toast queue so the `<Toaster>` component renders every toast.
 */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastContextProvider");
  }
  return ctx;
}

/**
 * Hook that creates the toast state — called once in the provider.
 * @internal
 */
export function useToastState(): ToastContextValue {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({
      title,
      description,
      variant = "default",
    }: {
      title: string;
      description?: string;
      variant?: ToastVariant;
    }) => {
      const id = String(++toastCount);
      setToasts((prev) => [...prev, { id, title, description, variant }]);
      const timer = setTimeout(() => {
        timersRef.current.delete(id);
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 5000);
      timersRef.current.set(id, timer);
    },
    [],
  );

  return { toasts, toast, dismiss };
}
