"use client";

import { useAuth } from "@/context/AuthContext";

/**
 * Check whether the current user holds the given permission code.
 *
 * ```tsx
 * const canWrite = usePermission("journal:write");
 * ```
 */
export function usePermission(code: string): boolean {
  const { user } = useAuth();
  if (!user) return false;
  return user.permissions?.includes(code) ?? false;
}

/**
 * Check whether the current user holds *all* of the listed permission codes.
 */
export function usePermissions(...codes: string[]): boolean {
  const { user } = useAuth();
  if (!user) return false;
  const perms = user.permissions ?? [];
  return codes.every((c) => perms.includes(c));
}
