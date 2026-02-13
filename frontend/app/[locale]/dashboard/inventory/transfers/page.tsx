"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  ArrowLeftRight,
  Plus,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
  Search,
} from "lucide-react";
import api from "@/lib/api";
import { fmtDate } from "@/lib/format";
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

interface Product {
  id: string;
  name: string;
  sku: string;
  current_stock: number;
}

interface TransferItem {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
}

interface Transfer {
  id: string;
  from_warehouse_id: string;
  from_warehouse_name: string;
  to_warehouse_id: string;
  to_warehouse_name: string;
  status: string;
  notes: string | null;
  items: TransferItem[];
  created_by_username: string;
  created_at: string;
  updated_at: string;
}

interface DraftItem {
  product_id: string;
  quantity: string;
  productSearch: string;
  dropdownOpen: boolean;
}

type TransferStatus = "PENDING" | "SHIPPED" | "RECEIVED" | "CANCELLED";

const STATUS_COLORS: Record<TransferStatus, string> = {
  PENDING: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  SHIPPED: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  RECEIVED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  CANCELLED: "bg-gray-100 text-gray-700 dark:bg-gray-900/40 dark:text-gray-300",
};

const STATUS_KEY: Record<TransferStatus, string> = {
  PENDING: "pending",
  SHIPPED: "shipped",
  RECEIVED: "received",
  CANCELLED: "cancelled",
};

// ─── Page ────────────────────────────────────────────────────────────────────

export default function TransfersPage() {
  const t = useTranslations("transfers");
  const tc = useTranslations("common");
  const locale = useLocale();
  const queryClient = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────────
  const [modalOpen, setModalOpen] = useState(false);
  const [fromWarehouseId, setFromWarehouseId] = useState("");
  const [toWarehouseId, setToWarehouseId] = useState("");
  const [draftItems, setDraftItems] = useState<DraftItem[]>([
    { product_id: "", quantity: "", productSearch: "", dropdownOpen: false },
  ]);
  const [notes, setNotes] = useState("");

  // Toast
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: transfers = [], isLoading } = useQuery<Transfer[]>({
    queryKey: ["transfers"],
    queryFn: () => api.get("/api/v1/warehouses/transfers").then((r) => r.data),
  });

  const { data: warehouses = [] } = useQuery<WarehouseData[]>({
    queryKey: ["warehouses"],
    queryFn: () => api.get("/api/v1/warehouses").then((r) => r.data),
  });

  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: () => api.get("/api/v1/inventory/products").then((r) => r.data),
  });

  const toWarehouseOptions = useMemo(
    () => warehouses.filter((w) => w.id !== fromWarehouseId),
    [warehouses, fromWarehouseId],
  );

  // ── Mutations ──────────────────────────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/warehouses/transfers", {
        from_warehouse_id: fromWarehouseId,
        to_warehouse_id: toWarehouseId,
        items: draftItems
          .filter((di) => di.product_id && Number(di.quantity) > 0)
          .map((di) => ({ product_id: di.product_id, quantity: Number(di.quantity) })),
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transfers"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setModalOpen(false);
      showToast(t("success"), "success");
    },
    onError: () => showToast(t("failed"), "error"),
  });

  const shipMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/warehouses/transfers/${id}/ship`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transfers"] });
      showToast(t("shipSuccess"), "success");
    },
    onError: () => showToast(t("shipFailed"), "error"),
  });

  const receiveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/warehouses/transfers/${id}/receive`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transfers"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      showToast(t("receiveSuccess"), "success");
    },
    onError: () => showToast(t("receiveFailed"), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/warehouses/transfers/${id}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transfers"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      showToast(t("cancelSuccess"), "success");
    },
    onError: () => showToast(t("cancelFailed"), "error"),
  });

  // ── Draft item helpers ──────────────────────────────────────────────────────
  const updateDraftItem = (index: number, patch: Partial<DraftItem>) => {
    setDraftItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };

  const addDraftItem = () => {
    setDraftItems((prev) => [
      ...prev,
      { product_id: "", quantity: "", productSearch: "", dropdownOpen: false },
    ]);
  };

  const removeDraftItem = (index: number) => {
    setDraftItems((prev) => prev.filter((_, i) => i !== index));
  };

  const filteredProducts = (search: string) => {
    if (!search.trim()) return products;
    const q = search.toLowerCase();
    return products.filter(
      (p) => p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q),
    );
  };

  const resetForm = () => {
    setFromWarehouseId("");
    setToWarehouseId("");
    setDraftItems([{ product_id: "", quantity: "", productSearch: "", dropdownOpen: false }]);
    setNotes("");
  };

  const openModal = () => {
    resetForm();
    setModalOpen(true);
  };

  const validItems = draftItems.filter((di) => di.product_id && Number(di.quantity) > 0);
  const canSubmit =
    fromWarehouseId &&
    toWarehouseId &&
    fromWarehouseId !== toWarehouseId &&
    validItems.length > 0 &&
    !createMutation.isPending;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ArrowLeftRight className="size-6 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        <Button onClick={openModal}>
          <Plus className="size-4" />
          {t("newTransfer")}
        </Button>
      </div>

      {/* Transfer List Table */}
      <div className="rounded-lg border bg-card">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <span className="ltr:ml-2 rtl:mr-2 text-sm text-muted-foreground">{t("loading")}</span>
          </div>
        ) : transfers.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-muted-foreground">
            {t("noTransfers")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-muted-foreground">
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("date")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("fromWarehouse")} → {t("toWarehouse")}</th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("items")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("status")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("createdBy")}</th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((tr) => {
                  const st = tr.status as TransferStatus;
                  return (
                    <tr key={tr.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-3 whitespace-nowrap">
                        {fmtDate(tr.created_at, locale)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-medium">{tr.from_warehouse_name}</span>
                        <span className="mx-2 text-muted-foreground">→</span>
                        <span className="font-medium">{tr.to_warehouse_name}</span>
                      </td>
                      <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums">
                        {tr.items.length}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                            STATUS_COLORS[st] ?? "bg-gray-100 text-gray-700",
                          )}
                        >
                          {t(STATUS_KEY[st] ?? "pending")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {tr.created_by_username}
                      </td>
                      <td className="px-4 py-3 ltr:text-right rtl:text-left space-x-1 rtl:space-x-reverse whitespace-nowrap">
                        {st === "PENDING" && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => shipMutation.mutate(tr.id)}
                              disabled={shipMutation.isPending}
                            >
                              {t("ship")}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => cancelMutation.mutate(tr.id)}
                              disabled={cancelMutation.isPending}
                            >
                              {t("cancel")}
                            </Button>
                          </>
                        )}
                        {st === "SHIPPED" && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => receiveMutation.mutate(tr.id)}
                              disabled={receiveMutation.isPending}
                            >
                              {t("receive")}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => cancelMutation.mutate(tr.id)}
                              disabled={cancelMutation.isPending}
                            >
                              {t("cancel")}
                            </Button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── New Transfer Dialog ────────────────────────────────────────────── */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("newTransfer")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* From / To Warehouse */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">{t("fromWarehouse")}</label>
                <select
                  value={fromWarehouseId}
                  onChange={(e) => {
                    setFromWarehouseId(e.target.value);
                    if (e.target.value === toWarehouseId) setToWarehouseId("");
                  }}
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">{t("selectWarehouse")}</option>
                  {warehouses.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">{t("toWarehouse")}</label>
                <select
                  value={toWarehouseId}
                  onChange={(e) => setToWarehouseId(e.target.value)}
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">{t("selectWarehouse")}</option>
                  {toWarehouseOptions.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Items */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("items")}</label>
              <div className="space-y-2">
                {draftItems.map((di, idx) => {
                  const selectedProduct = products.find((p) => p.id === di.product_id);
                  const filtered = filteredProducts(di.productSearch);
                  return (
                    <div key={idx} className="flex items-start gap-2">
                      {/* Product Searchable Dropdown */}
                      <div className="relative flex-1">
                        <div className="relative">
                          <Search className="absolute ltr:left-3 rtl:right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                          <input
                            type="text"
                            value={
                              selectedProduct
                                ? `${selectedProduct.sku} — ${selectedProduct.name}`
                                : di.productSearch
                            }
                            onChange={(e) => {
                              updateDraftItem(idx, {
                                productSearch: e.target.value,
                                product_id: "",
                                dropdownOpen: true,
                              });
                            }}
                            onFocus={() => updateDraftItem(idx, { dropdownOpen: true })}
                            placeholder={t("product")}
                            className="h-10 w-full rounded-md border bg-background ltr:pl-9 rtl:pr-9 ltr:pr-3 rtl:pl-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                          />
                        </div>
                        {di.dropdownOpen && !di.product_id && (
                          <div className="absolute z-10 mt-1 max-h-40 w-full overflow-auto rounded-md border bg-popover shadow-md">
                            {filtered.length === 0 ? (
                              <div className="px-3 py-2 text-sm text-muted-foreground">
                                {tc("noData")}
                              </div>
                            ) : (
                              filtered.map((p) => (
                                <button
                                  key={p.id}
                                  type="button"
                                  className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-accent text-left rtl:text-right"
                                  onClick={() => {
                                    updateDraftItem(idx, {
                                      product_id: p.id,
                                      productSearch: "",
                                      dropdownOpen: false,
                                    });
                                  }}
                                >
                                  <span>
                                    <span className="font-mono text-xs text-muted-foreground">
                                      {p.sku}
                                    </span>
                                    {" — "}
                                    {p.name}
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {p.current_stock}
                                  </span>
                                </button>
                              ))
                            )}
                          </div>
                        )}
                      </div>

                      {/* Quantity */}
                      <input
                        type="number"
                        min="1"
                        value={di.quantity}
                        onChange={(e) => updateDraftItem(idx, { quantity: e.target.value })}
                        placeholder={t("quantity")}
                        className="h-10 w-24 rounded-md border bg-background px-3 text-sm tabular-nums placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />

                      {/* Remove */}
                      {draftItems.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-1 text-destructive"
                          onClick={() => removeDraftItem(idx)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
              <Button variant="outline" size="sm" className="mt-2" onClick={addDraftItem}>
                <Plus className="size-3.5" />
                {t("addItem")}
              </Button>
            </div>

            {/* Notes */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("notes")}</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("notesPlaceholder")}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button disabled={!canSubmit} onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? t("submitting") : t("submit")}
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
