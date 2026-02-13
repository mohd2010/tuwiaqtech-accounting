"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { FileCheck, Plus, Trash2, CheckCircle, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Product {
  id: string;
  name: string;
  sku: string;
  unit_price: string;
  current_stock: number;
}

interface QuoteLineItem {
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function CreateQuotePage() {
  const t = useTranslations("quotes");
  const locale = useLocale();
  const router = useRouter();

  // Customer info
  const [customerName, setCustomerName] = useState("");
  const [customerVat, setCustomerVat] = useState("");
  const [expiryDate, setExpiryDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().slice(0, 10);
  });
  const [notes, setNotes] = useState("");

  // Line items
  const [lineItems, setLineItems] = useState<QuoteLineItem[]>([]);
  const [selectedProductId, setSelectedProductId] = useState("");

  // Toast
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Fetch products
  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: () => api.get("/api/v1/inventory/products").then((r) => r.data),
  });

  // Add item
  const handleAddItem = () => {
    if (!selectedProductId) return;
    const product = products.find((p) => p.id === selectedProductId);
    if (!product) return;

    // Don't add duplicates
    if (lineItems.some((li) => li.product_id === product.id)) return;

    setLineItems((prev) => [
      ...prev,
      {
        product_id: product.id,
        product_name: product.name,
        quantity: 1,
        unit_price: Number(product.unit_price),
      },
    ]);
    setSelectedProductId("");
  };

  const updateItemQty = (idx: number, qty: number) => {
    setLineItems((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, quantity: Math.max(1, qty) } : item)),
    );
  };

  const updateItemPrice = (idx: number, price: number) => {
    setLineItems((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, unit_price: Math.max(0, price) } : item)),
    );
  };

  const removeItem = (idx: number) => {
    setLineItems((prev) => prev.filter((_, i) => i !== idx));
  };

  // Totals
  const grandTotal = lineItems.reduce(
    (sum, item) => sum + item.unit_price * item.quantity,
    0,
  );
  const vatAmount = (grandTotal * 15) / 115;
  const netAmount = grandTotal - vatAmount;

  const canSubmit = customerName.trim() && lineItems.length > 0;

  // Submit
  const mutation = useMutation({
    mutationFn: async () => {
      const res = await api.post("/api/v1/quotes", {
        customer_name: customerName.trim(),
        customer_vat: customerVat.trim() || null,
        expiry_date: expiryDate,
        notes: notes.trim() || null,
        items: lineItems.map((li) => ({
          product_id: li.product_id,
          quantity: li.quantity,
          unit_price: li.unit_price.toFixed(4),
        })),
      });
      return res.data;
    },
    onSuccess: (data) => {
      showToast(t("createSuccess"), "success");
      router.push(`/dashboard/quotes/${data.id}` as "/dashboard/quotes");
    },
    onError: () => {
      showToast(t("createFailed"), "error");
    },
  });

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <FileCheck className="size-7 text-primary" />
        <h1 className="text-3xl font-bold">{t("createTitle")}</h1>
      </div>

      {/* Customer Info */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">{t("quoteInfo")}</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium">{t("customerName")}</label>
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder={t("customerNamePlaceholder")}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("customerVat")}</label>
            <input
              type="text"
              value={customerVat}
              onChange={(e) => setCustomerVat(e.target.value)}
              placeholder={t("customerVatPlaceholder")}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("expiryDate")}</label>
            <input
              type="date"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("notes")}</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("notesPlaceholder")}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
      </div>

      {/* Line Items */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">{t("addProducts")}</h2>

        {/* Add item row */}
        <div className="mb-4 flex gap-2">
          <select
            value={selectedProductId}
            onChange={(e) => setSelectedProductId(e.target.value)}
            className="h-10 flex-1 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{t("selectProduct")}</option>
            {products
              .filter((p) => !lineItems.some((li) => li.product_id === p.id))
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} — {p.name} ({Number(p.unit_price).toFixed(2)} SAR)
                </option>
              ))}
          </select>
          <Button onClick={handleAddItem} disabled={!selectedProductId}>
            <Plus className="size-4 ltr:mr-1 rtl:ml-1" />
            {t("addItem")}
          </Button>
        </div>

        {/* Items table */}
        {lineItems.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 ltr:text-left rtl:text-right font-semibold">{t("product")}</th>
                  <th className="pb-2 text-center font-semibold w-24">{t("qty")}</th>
                  <th className="pb-2 text-center font-semibold w-36">{t("unitPrice")}</th>
                  <th className="pb-2 ltr:text-right rtl:text-left font-semibold">{t("lineTotal")}</th>
                  <th className="pb-2 w-16"></th>
                </tr>
              </thead>
              <tbody>
                {lineItems.map((item, idx) => (
                  <tr key={item.product_id} className="border-b last:border-0">
                    <td className="py-3 font-medium">{item.product_name}</td>
                    <td className="py-3">
                      <input
                        type="number"
                        min="1"
                        value={item.quantity}
                        onChange={(e) => updateItemQty(idx, parseInt(e.target.value) || 1)}
                        className="h-8 w-full rounded border bg-background px-2 text-center text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </td>
                    <td className="py-3">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={item.unit_price}
                        onChange={(e) => updateItemPrice(idx, parseFloat(e.target.value) || 0)}
                        className="h-8 w-full rounded border bg-background px-2 text-center text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </td>
                    <td className="py-3 ltr:text-right rtl:text-left tabular-nums font-medium">
                      {(item.unit_price * item.quantity).toFixed(2)} SAR
                    </td>
                    <td className="py-3 text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 text-destructive hover:text-destructive"
                        onClick={() => removeItem(idx)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Totals */}
        {lineItems.length > 0 && (
          <div className="mt-4 ltr:ml-auto rtl:mr-auto w-64 space-y-1.5 text-sm">
            <div className="flex justify-between text-muted-foreground">
              <span>{t("subtotalExclVat")}</span>
              <span className="tabular-nums">{netAmount.toFixed(2)} SAR</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>{t("vat15")}</span>
              <span className="tabular-nums">{vatAmount.toFixed(2)} SAR</span>
            </div>
            <div className="flex justify-between border-t pt-2 text-lg font-bold">
              <span>{t("total")}</span>
              <span className="tabular-nums">{grandTotal.toFixed(2)} SAR</span>
            </div>
          </div>
        )}
      </div>

      {/* Submit */}
      <Button
        className="w-full"
        size="lg"
        disabled={!canSubmit || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? t("saving") : t("saveQuote")}
      </Button>

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
          {toast.type === "error" && <AlertCircle className="size-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
}
