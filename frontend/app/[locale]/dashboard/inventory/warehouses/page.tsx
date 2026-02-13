"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  Warehouse as WarehouseIcon,
  Plus,
  Pencil,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface WarehouseData {
  id: string;
  name: string;
  address: string | null;
  is_active: boolean;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function WarehousesPage() {
  const t = useTranslations("warehouses");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────────
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [isActive, setIsActive] = useState(true);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: warehouses = [], isLoading } = useQuery<WarehouseData[]>({
    queryKey: ["warehouses"],
    queryFn: () => api.get("/api/v1/warehouses").then((r) => r.data),
  });

  // ── Mutations ──────────────────────────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/warehouses", {
        name: name.trim(),
        address: address.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["warehouses"] });
      setModalOpen(false);
      showToast(t("success"), "success");
    },
    onError: () => showToast(t("failed"), "error"),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api.patch(`/api/v1/warehouses/${editingId}`, {
        name: name.trim(),
        address: address.trim() || null,
        is_active: isActive,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["warehouses"] });
      setModalOpen(false);
      showToast(t("success"), "success");
    },
    onError: () => showToast(t("failed"), "error"),
  });

  const isPending = createMutation.isPending || updateMutation.isPending;

  const resetForm = () => {
    setEditingId(null);
    setName("");
    setAddress("");
    setIsActive(true);
  };

  const openCreate = () => {
    resetForm();
    setModalOpen(true);
  };

  const openEdit = (wh: WarehouseData) => {
    setEditingId(wh.id);
    setName(wh.name);
    setAddress(wh.address ?? "");
    setIsActive(wh.is_active);
    setModalOpen(true);
  };

  const handleSubmit = () => {
    if (editingId) {
      updateMutation.mutate();
    } else {
      createMutation.mutate();
    }
  };

  const canSubmit = name.trim().length > 0 && !isPending;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <WarehouseIcon className="size-6 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t("addWarehouse")}
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-lg border bg-card">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <span className="ltr:ml-2 rtl:mr-2 text-sm text-muted-foreground">{t("loading")}</span>
          </div>
        ) : warehouses.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-muted-foreground">
            {t("noWarehouses")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-muted-foreground">
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("name")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("address")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("status")}</th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {warehouses.map((wh) => (
                  <tr key={wh.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">{wh.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{wh.address ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          wh.is_active
                            ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                            : "bg-gray-100 text-gray-700 dark:bg-gray-900/40 dark:text-gray-300",
                        )}
                      >
                        {wh.is_active ? t("active") : t("inactive")}
                      </span>
                    </td>
                    <td className="px-4 py-3 ltr:text-right rtl:text-left">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(wh)}>
                        <Pencil className="size-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Create / Edit Dialog ──────────────────────────────────────────── */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingId ? t("editWarehouse") : t("createWarehouse")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Name */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("name")}</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("name")}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Address */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("address")}</label>
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder={t("address")}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>

            {/* Active (only for edit) */}
            {editingId && (
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="size-4 rounded border"
                />
                <label htmlFor="is_active" className="text-sm font-medium">
                  {t("active")}
                </label>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button disabled={!canSubmit} onClick={handleSubmit}>
              {isPending ? t("creating") : tc("save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Toast ──────────────────────────────────────────────────────────── */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 ltr:right-6 rtl:left-6 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg",
            toast.type === "success" ? "bg-green-600 text-white" : "bg-red-600 text-white",
          )}
        >
          {toast.type === "success" && <CheckCircle className="size-4" />}
          {toast.type === "error" && <AlertCircle className="size-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
}
