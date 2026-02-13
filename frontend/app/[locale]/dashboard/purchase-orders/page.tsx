"use client";

import { useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  Plus,
  Trash2,
  PackageCheck,
  XCircle,
  CheckCircle,
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
import { fmtNumber, fmtDate } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Supplier {
  id: string;
  name: string;
}

interface Product {
  id: string;
  name: string;
  sku: string;
  cost_price: string;
}

interface POItem {
  id: string;
  product_id: string;
  quantity: number;
  unit_cost: string;
}

interface PurchaseOrder {
  id: string;
  supplier_id: string;
  status: string;
  total_amount: string;
  created_at: string;
  items: POItem[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  PENDING:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  RECEIVED:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  CANCELLED:
    "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PurchaseOrdersPage() {
  const queryClient = useQueryClient();
  const t = useTranslations("purchaseOrders");
  const tc = useTranslations("common");
  const locale = useLocale();
  const fmt = (v: string | number) => fmtNumber(v, locale);

  const [showCreate, setShowCreate] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const showToast = useCallback(
    (message: string, type: "success" | "error") => {
      setToast({ message, type });
      setTimeout(() => setToast(null), 3000);
    },
    [],
  );

  const { data: orders = [], isLoading } = useQuery<PurchaseOrder[]>({
    queryKey: ["purchase-orders"],
    queryFn: () => api.get("/api/v1/purchase-orders/").then((r) => r.data),
  });

  const { data: suppliers = [] } = useQuery<Supplier[]>({
    queryKey: ["suppliers"],
    queryFn: () => api.get("/api/v1/suppliers/").then((r) => r.data),
  });

  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: () => api.get("/api/v1/inventory/products").then((r) => r.data),
  });

  const supplierMap = Object.fromEntries(
    suppliers.map((s) => [s.id, s.name]),
  );
  const productMap = Object.fromEntries(
    products.map((p) => [p.id, p.name]),
  );

  const receiveMutation = useMutation({
    mutationFn: (poId: string) =>
      api.patch(`/api/v1/purchase-orders/${poId}/receive`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      showToast(t("shipmentReceived"), "success");
    },
    onError: () => showToast(t("failedReceive"), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (poId: string) =>
      api.patch(`/api/v1/purchase-orders/${poId}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      showToast(t("orderCancelled"), "success");
    },
    onError: () => showToast(t("failedCancel"), "error"),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="size-4" />
          {t("newPO")}
        </Button>
      </div>

      {/* PO Table */}
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("date")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("supplier")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("items")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("total")}</th>
              <th className="px-4 py-3 text-center font-medium">{t("status")}</th>
              <th className="px-4 py-3 text-right font-medium">{tc("actions")}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  {tc("loading")}
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  {t("noPOs")}
                </td>
              </tr>
            ) : (
              orders.map((po) => (
                <tr
                  key={po.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    {fmtDate(po.created_at, locale)}
                  </td>
                  <td className="px-4 py-3 font-medium">
                    {supplierMap[po.supplier_id] ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {po.items.map((i) => (
                      <span key={i.id} className="block text-xs">
                        {productMap[i.product_id] ?? i.product_id} x{i.quantity}
                      </span>
                    ))}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">
                    {fmt(po.total_amount)} SAR
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={cn(
                        "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold",
                        STATUS_STYLES[po.status] ?? "",
                      )}
                    >
                      {po.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {po.status === "PENDING" && (
                      <div className="flex justify-end gap-1">
                        <Button
                          size="xs"
                          onClick={() => receiveMutation.mutate(po.id)}
                          disabled={receiveMutation.isPending}
                        >
                          <PackageCheck className="size-3" />
                          {t("receive")}
                        </Button>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => cancelMutation.mutate(po.id)}
                          disabled={cancelMutation.isPending}
                          className="text-destructive hover:text-destructive"
                        >
                          <XCircle className="size-3" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create PO dialog */}
      {showCreate && (
        <CreatePODialog
          suppliers={suppliers}
          products={products}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
            setShowCreate(false);
            showToast(t("orderCreated"), "success");
          }}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 ltr:right-6 rtl:left-6 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg",
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white",
          )}
        >
          {toast.type === "success" && <CheckCircle className="size-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
}

// ─── Create PO Dialog ────────────────────────────────────────────────────────

interface LineItem {
  product_id: string;
  quantity: number;
  unit_cost: number;
}

function CreatePODialog({
  suppliers,
  products,
  onClose,
  onSuccess,
}: {
  suppliers: Supplier[];
  products: Product[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const t = useTranslations("purchaseOrders");
  const tc = useTranslations("common");
  const locale = useLocale();
  const fmt = (v: string | number) => fmtNumber(v, locale);

  const [supplierId, setSupplierId] = useState("");
  const [lines, setLines] = useState<LineItem[]>([
    { product_id: "", quantity: 1, unit_cost: 0 },
  ]);
  const [error, setError] = useState("");

  const addLine = () =>
    setLines((prev) => [...prev, { product_id: "", quantity: 1, unit_cost: 0 }]);

  const removeLine = (idx: number) =>
    setLines((prev) => prev.filter((_, i) => i !== idx));

  const updateLine = (idx: number, field: keyof LineItem, value: string | number) =>
    setLines((prev) =>
      prev.map((line, i) => (i === idx ? { ...line, [field]: value } : line)),
    );

  const onProductSelect = (idx: number, productId: string) => {
    const product = products.find((p) => p.id === productId);
    setLines((prev) =>
      prev.map((line, i) =>
        i === idx
          ? {
              ...line,
              product_id: productId,
              unit_cost: product ? Number(product.cost_price) : 0,
            }
          : line,
      ),
    );
  };

  const total = lines.reduce(
    (sum, l) => sum + l.quantity * l.unit_cost,
    0,
  );

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/purchase-orders/", {
        supplier_id: supplierId,
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity: l.quantity,
          unit_cost: l.unit_cost,
        })),
      }),
    onSuccess,
    onError: () => setError(t("failedCreatePO")),
  });

  const canSubmit =
    supplierId !== "" &&
    lines.length > 0 &&
    lines.every((l) => l.product_id !== "" && l.quantity > 0 && l.unit_cost >= 0);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("newPO")}</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mutation.mutate();
          }}
          className="space-y-4"
        >
          {/* Supplier */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t("supplier")} *
            </label>
            <select
              required
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">{t("selectSupplier")}</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Line items */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm font-medium">{t("items")} *</label>
              <Button type="button" size="xs" variant="outline" onClick={addLine}>
                <Plus className="size-3" />
                {t("addItem")}
              </Button>
            </div>

            <div className="space-y-2">
              {lines.map((line, idx) => (
                <div
                  key={idx}
                  className="flex items-end gap-2 rounded-md border border-border/50 bg-muted/20 p-3"
                >
                  {/* Product */}
                  <div className="flex-1 min-w-0">
                    <label className="mb-1 block text-xs text-muted-foreground">
                      {t("product")}
                    </label>
                    <select
                      required
                      value={line.product_id}
                      onChange={(e) => onProductSelect(idx, e.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">{tc("select")}</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.sku})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Quantity */}
                  <div className="w-24">
                    <label className="mb-1 block text-xs text-muted-foreground">
                      {t("qty")}
                    </label>
                    <input
                      type="number"
                      min={1}
                      required
                      value={line.quantity}
                      onChange={(e) =>
                        updateLine(idx, "quantity", parseInt(e.target.value) || 1)
                      }
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Unit Cost */}
                  <div className="w-32">
                    <label className="mb-1 block text-xs text-muted-foreground">
                      {t("unitCost")}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min={0}
                      required
                      value={line.unit_cost}
                      onChange={(e) =>
                        updateLine(
                          idx,
                          "unit_cost",
                          parseFloat(e.target.value) || 0,
                        )
                      }
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Line total */}
                  <div className="w-28 text-right">
                    <label className="mb-1 block text-xs text-muted-foreground">
                      {t("subtotal")}
                    </label>
                    <p className="py-2 text-sm font-medium tabular-nums">
                      {fmt(line.quantity * line.unit_cost)}
                    </p>
                  </div>

                  {/* Remove */}
                  {lines.length > 1 && (
                    <Button
                      type="button"
                      size="icon-xs"
                      variant="ghost"
                      onClick={() => removeLine(idx)}
                      className="mb-1 text-destructive hover:text-destructive"
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Total */}
          <div className="flex justify-end border-t pt-3">
            <div className="text-right">
              <span className="text-sm text-muted-foreground">
                {t("orderTotal")}
              </span>
              <p className="text-lg font-bold tabular-nums">
                {fmt(total)} SAR
              </p>
            </div>
          </div>

          {error && (
            <p className="text-center text-sm text-red-500">{error}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {tc("cancel")}
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit || mutation.isPending}
            >
              {mutation.isPending ? tc("loading") : t("createOrder")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
