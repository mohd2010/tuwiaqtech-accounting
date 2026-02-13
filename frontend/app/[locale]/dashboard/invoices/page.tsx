"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface CustomerOption {
  id: string;
  name: string;
}

interface ProductOption {
  id: string;
  name: string;
  sku: string;
  unit_price: string;
  current_stock: number;
}

interface CreditInvoice {
  id: string;
  customer_id: string;
  customer_name: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  total_amount: string;
  amount_paid: string;
  status: string;
}

interface LineItem {
  product_id: string;
  quantity: number;
}

export default function InvoicesPage() {
  const t = useTranslations("invoices");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [lineItems, setLineItems] = useState<LineItem[]>([{ product_id: "", quantity: 1 }]);

  // Fetch invoices
  const { data: invoices, isLoading } = useQuery<CreditInvoice[]>({
    queryKey: ["credit-invoices", statusFilter],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (statusFilter !== "ALL") params.status = statusFilter;
      return api.get("/api/v1/invoices/", { params }).then((r) => r.data);
    },
  });

  // Fetch customers for dropdown
  const { data: customers } = useQuery<CustomerOption[]>({
    queryKey: ["customers-list"],
    queryFn: () => api.get("/api/v1/customers").then((r) => r.data),
  });

  // Fetch products for dropdown
  const { data: products } = useQuery<ProductOption[]>({
    queryKey: ["products-list"],
    queryFn: () => api.get("/api/v1/inventory").then((r) => r.data),
  });

  // Create mutation
  const createMut = useMutation({
    mutationFn: (body: { customer_id: string; items: LineItem[] }) =>
      api.post("/api/v1/invoices/credit", body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credit-invoices"] });
      setShowCreate(false);
      setSelectedCustomer("");
      setLineItems([{ product_id: "", quantity: 1 }]);
    },
  });

  const handleCreate = () => {
    if (!selectedCustomer || lineItems.some((li) => !li.product_id || li.quantity < 1)) return;
    createMut.mutate({
      customer_id: selectedCustomer,
      items: lineItems,
    });
  };

  const addLineItem = () => setLineItems([...lineItems, { product_id: "", quantity: 1 }]);
  const removeLineItem = (idx: number) => setLineItems(lineItems.filter((_, i) => i !== idx));
  const updateLineItem = (idx: number, field: keyof LineItem, value: string | number) => {
    const updated = [...lineItems];
    if (field === "quantity") {
      updated[idx].quantity = Number(value);
    } else {
      updated[idx].product_id = value as string;
    }
    setLineItems(updated);
  };

  const statusBadge = (inv: CreditInvoice) => {
    const isOverdue = inv.status !== "PAID" && new Date(inv.due_date) < new Date();
    if (isOverdue) {
      return (
        <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-300">
          {t("statusOverdue")}
        </span>
      );
    }
    const colors: Record<string, string> = {
      OPEN: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
      PARTIAL: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
      PAID: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
    };
    const labels: Record<string, string> = {
      OPEN: t("statusOpen"),
      PARTIAL: t("statusPartial"),
      PAID: t("statusPaid"),
    };
    return (
      <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", colors[inv.status])}>
        {labels[inv.status]}
      </span>
    );
  };

  if (isLoading) {
    return <p className="text-muted-foreground">{t("loadingInvoices")}</p>;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {t("createInvoice")}
        </Button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="mb-6 rounded-lg border bg-card p-5">
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium">{t("selectCustomer")}</label>
            <Select value={selectedCustomer} onValueChange={setSelectedCustomer}>
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder={t("selectCustomer")} />
              </SelectTrigger>
              <SelectContent>
                {customers?.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {lineItems.map((li, idx) => (
            <div key={idx} className="mb-2 flex items-center gap-3">
              <Select
                value={li.product_id}
                onValueChange={(v) => updateLineItem(idx, "product_id", v)}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder={t("selectProduct")} />
                </SelectTrigger>
                <SelectContent>
                  {products?.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <input
                type="number"
                min={1}
                value={li.quantity}
                onChange={(e) => updateLineItem(idx, "quantity", e.target.value)}
                className="w-20 rounded-md border bg-background px-3 py-2 text-sm"
              />
              {lineItems.length > 1 && (
                <Button variant="ghost" size="sm" onClick={() => removeLineItem(idx)}>
                  {t("removeItem")}
                </Button>
              )}
            </div>
          ))}

          <div className="mt-3 flex gap-3">
            <Button variant="outline" size="sm" onClick={addLineItem}>
              {t("addItem")}
            </Button>
            <Button
              onClick={handleCreate}
              disabled={createMut.isPending || !selectedCustomer}
            >
              {createMut.isPending ? "..." : t("createInvoice")}
            </Button>
          </div>
          {createMut.isError && (
            <p className="mt-2 text-sm text-red-600">{t("createFailed")}</p>
          )}
          {createMut.isSuccess && (
            <p className="mt-2 text-sm text-green-600">{t("createSuccess")}</p>
          )}
        </div>
      )}

      {/* Status filter */}
      <div className="mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder={t("filterByStatus")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">{t("filterAll")}</SelectItem>
            <SelectItem value="OPEN">{t("statusOpen")}</SelectItem>
            <SelectItem value="PARTIAL">{t("statusPartial")}</SelectItem>
            <SelectItem value="PAID">{t("statusPaid")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Invoices Table */}
      {!invoices || invoices.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noInvoices")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("invoiceNumber")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("customer")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("invoiceDate")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("dueDate")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("totalAmount")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("amountPaid")}</th>
                <th className="px-4 py-3 text-center font-medium">{t("status")}</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/dashboard/invoices/${inv.id}` as "/dashboard/invoices"}
                      className="font-medium text-primary hover:underline"
                    >
                      {inv.invoice_number}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">{inv.customer_name}</td>
                  <td className="px-4 py-2.5 text-xs">{fmtDate(inv.invoice_date, locale)}</td>
                  <td className="px-4 py-2.5 text-xs">{fmtDate(inv.due_date, locale)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(inv.total_amount)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(inv.amount_paid)}</td>
                  <td className="px-4 py-2.5 text-center">{statusBadge(inv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
