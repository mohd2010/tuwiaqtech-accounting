"use client";

import { useAuth } from "@/context/AuthContext";
import { usePermission } from "@/hooks/usePermission";

interface PermissionGuardProps {
  /** Permission code required to render children */
  permission: string;
  /** Rendered when user lacks the permission (defaults to nothing) */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Conditionally render children based on user permissions.
 *
 * While auth is loading, renders nothing (avoids flashing the fallback).
 *
 * ```tsx
 * <PermissionGuard permission="journal:write">
 *   <Button>Create Entry</Button>
 * </PermissionGuard>
 * ```
 */
export function PermissionGuard({
  permission,
  fallback = null,
  children,
}: PermissionGuardProps) {
  const { loading } = useAuth();
  const allowed = usePermission(permission);

  if (loading) return null;
  return allowed ? <>{children}</> : <>{fallback}</>;
}
