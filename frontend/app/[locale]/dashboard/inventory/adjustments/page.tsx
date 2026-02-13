"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  ClipboardMinus,
  Plus,
  ArrowDown,
  ArrowUp,
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

interface Product {
  id: string;
  name: string;
  sku: string;
  current_stock: number;
  cost_price: string;
}

interface Adjustment {
  id: string;
  product_name: string;
  product_sku: string;
  adjustment_type: string;
  quantity: number;
  notes: string | null;
  created_by_username: string;
  created_at: string;
}

type AdjType = "DAMAGE" | "THEFT" | "COUNT_ERROR" | "PROMOTION";

const ADJ_TYPES: AdjType[] = ["DAMAGE", "THEFT", "COUNT_ERROR", "PROMOTION"];

const TYPE_LABEL_KEY: Record<AdjType, string> = {
  DAMAGE: "damage",
  THEFT: "theft",
  COUNT_ERROR: "countError",
  PROMOTION: "promotion",
};

const TYPE_COLORS: Record<AdjType, string> = {
  DAMAGE: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  THEFT: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  COUNT_ERROR: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  PROMOTION: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
};

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AdjustmentsPage() {
  const t = useTranslations("adjustments");
  const tc = useTranslations("common");
  const locale = useLocale();
  const queryClient = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────────
  const [modalOpen, setModalOpen] = useState(false);
  const [productId, setProductId] = useState("");
  const [adjType, setAdjType] = useState<AdjType>("DAMAGE");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: adjustments = [], isLoading } = useQuery<Adjustment[]>({
    queryKey: ["adjustments"],
    queryFn: () => api.get("/api/v1/inventory/adjustments").then((r) => r.data),
  });

  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: () => api.get("/api/v1/inventory/products").then((r) => r.data),
  });

  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return products;
    const q = productSearch.toLowerCase();
    return products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q),
    );
  }, [products, productSearch]);

  const selectedProduct = products.find((p) => p.id === productId);

  // ── Mutation ───────────────────────────────────────────────────────────────
  const mutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/inventory/adjustments", {
        product_id: productId,
        adjustment_type: adjType,
        quantity: Number(quantity),
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["adjustments"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setModalOpen(false);
      resetForm();
      showToast(t("success"), "success");
    },
    onError: () => showToast(t("failed"), "error"),
  });

  const resetForm = () => {
    setProductId("");
    setAdjType("DAMAGE");
    setQuantity("");
    setNotes("");
    setProductSearch("");
  };

  const openModal = () => {
    resetForm();
    setModalOpen(true);
  };

  const canSubmit =
    productId && Number(quantity) !== 0 && !mutation.isPending;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ClipboardMinus className="size-6 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        <Button onClick={openModal}>
          <Plus className="size-4" />
          {t("newAdjustment")}
        </Button>
      </div>

      {/* History Table */}
      <div className="rounded-lg border bg-card">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <span className="ltr:ml-2 rtl:mr-2 text-sm text-muted-foreground">{t("loading")}</span>
          </div>
        ) : adjustments.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-muted-foreground">
            {t("noAdjustments")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-muted-foreground">
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("date")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("product")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("adjustmentType")}</th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("qtyChange")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("reason")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("user")}</th>
                </tr>
              </thead>
              <tbody>
                {adjustments.map((adj) => (
                  <tr key={adj.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3 whitespace-nowrap">
                      {fmtDate(adj.created_at, locale)}
                    </td>
                    <td className="px-4 py-3">
                      <div>{adj.product_name}</div>
                      <div className="text-xs text-muted-foreground font-mono">{adj.product_sku}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          TYPE_COLORS[adj.adjustment_type as AdjType] ?? "bg-gray-100 text-gray-700",
                        )}
                      >
                        {t(TYPE_LABEL_KEY[adj.adjustment_type as AdjType] ?? "damage")}
                      </span>
                    </td>
                    <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums font-semibold">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1",
                          adj.quantity < 0 ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400",
                        )}
                      >
                        {adj.quantity < 0 ? (
                          <ArrowDown className="size-3.5" />
                        ) : (
                          <ArrowUp className="size-3.5" />
                        )}
                        {adj.quantity > 0 ? `+${adj.quantity}` : adj.quantity}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">
                      {adj.notes ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {adj.created_by_username}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── New Adjustment Dialog ─────────────────────────────────────────── */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("newAdjustment")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Product (Searchable Dropdown) */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("product")}</label>
              <div className="relative">
                <div className="relative">
                  <Search className="absolute ltr:left-3 rtl:right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={selectedProduct ? `${selectedProduct.sku} — ${selectedProduct.name}` : productSearch}
                    onChange={(e) => {
                      setProductSearch(e.target.value);
                      setProductId("");
                      setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    placeholder={t("searchProducts")}
                    className="h-10 w-full rounded-md border bg-background ltr:pl-9 rtl:pr-9 ltr:pr-3 rtl:pl-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                {dropdownOpen && !productId && (
                  <div className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-md border bg-popover shadow-md">
                    {filteredProducts.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-muted-foreground">{tc("noData")}</div>
                    ) : (
                      filteredProducts.map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-accent text-left rtl:text-right"
                          onClick={() => {
                            setProductId(p.id);
                            setProductSearch("");
                            setDropdownOpen(false);
                          }}
                        >
                          <span>
                            <span className="font-mono text-xs text-muted-foreground">{p.sku}</span>
                            {" — "}
                            {p.name}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {t("currentStock")}: {p.current_stock}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
              {selectedProduct && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("currentStock")}: {selectedProduct.current_stock}
                </p>
              )}
            </div>

            {/* Adjustment Type */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("adjustmentType")}</label>
              <select
                value={adjType}
                onChange={(e) => setAdjType(e.target.value as AdjType)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {ADJ_TYPES.map((at) => (
                  <option key={at} value={at}>
                    {t(TYPE_LABEL_KEY[at])}
                  </option>
                ))}
              </select>
            </div>

            {/* Quantity */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("quantity")}</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="e.g. -3"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm tabular-nums placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="mt-1 text-xs text-muted-foreground">{t("quantityHint")}</p>
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
            <Button disabled={!canSubmit} onClick={() => mutation.mutate()}>
              {mutation.isPending ? t("submitting") : t("submit")}
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
