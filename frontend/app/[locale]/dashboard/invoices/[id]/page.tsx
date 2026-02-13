"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
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

interface InvoicePayment {
  id: string;
  amount: string;
  payment_date: string;
  journal_entry_id: string;
}

interface InvoiceDetail {
  id: string;
  customer_id: string;
  customer_name: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  total_amount: string;
  amount_paid: string;
  status: string;
  journal_entry_id: string;
  payments: InvoicePayment[];
  items: { description: string; cost: string }[];
}

export default function InvoiceDetailPage() {
  const params = useParams();
  const invoiceId = params.id as string;
  const t = useTranslations("invoiceDetail");
  const tInv = useTranslations("invoices");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);
  const queryClient = useQueryClient();

  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("CASH");

  const { data, isLoading } = useQuery<InvoiceDetail>({
    queryKey: ["credit-invoice", invoiceId],
    queryFn: () =>
      api.get(`/api/v1/invoices/${invoiceId}`).then((r) => r.data),
  });

  const payMut = useMutation({
    mutationFn: (body: { invoice_id: string; amount: number; payment_method: string }) =>
      api.post("/api/v1/invoices/payment", body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credit-invoice", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["credit-invoices"] });
      setPayAmount("");
    },
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingDetail")}</p>;
  }

  const remaining = Number(data.total_amount) - Number(data.amount_paid);
  const isPaid = data.status === "PAID";
  const isOverdue = !isPaid && new Date(data.due_date) < new Date();

  const handlePay = () => {
    const amt = Number(payAmount);
    if (amt <= 0 || amt > remaining) return;
    payMut.mutate({
      invoice_id: invoiceId,
      amount: amt,
      payment_method: payMethod,
    });
  };

  const handlePayFull = () => {
    payMut.mutate({
      invoice_id: invoiceId,
      amount: remaining,
      payment_method: payMethod,
    });
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-3xl font-bold">{data.invoice_number}</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        {data.customer_name}
      </p>

      {/* Invoice summary card */}
      <div className="mb-6 rounded-lg border bg-card p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs text-muted-foreground">{tInv("invoiceDate")}</p>
            <p className="font-medium">{fmtDate(data.invoice_date, locale)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{tInv("dueDate")}</p>
            <p className={cn("font-medium", isOverdue && "text-red-600")}>
              {fmtDate(data.due_date, locale)}
              {isOverdue && ` (${tInv("statusOverdue")})`}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{tInv("totalAmount")}</p>
            <p className="text-lg font-bold">{fmt(data.total_amount)} SAR</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{tInv("amountPaid")}</p>
            <p className="text-lg font-bold">{fmt(data.amount_paid)} SAR</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{tInv("remaining")}</p>
            <p className={cn("text-lg font-bold", remaining > 0 && "text-amber-600")}>
              {fmt(String(remaining))} SAR
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{tInv("status")}</p>
            <p className="font-semibold">
              {isPaid ? tInv("statusPaid") : isOverdue ? tInv("statusOverdue") : data.status === "PARTIAL" ? tInv("statusPartial") : tInv("statusOpen")}
            </p>
          </div>
        </div>
      </div>

      {/* Payment form */}
      {isPaid ? (
        <div className="mb-6 rounded-lg border-2 border-green-500 bg-green-50 px-5 py-4 text-green-700 dark:bg-green-950/30 dark:text-green-400">
          <p className="font-semibold">{t("fullyPaid")}</p>
        </div>
      ) : (
        <div className="mb-6 rounded-lg border bg-card p-5">
          <h2 className="mb-3 text-lg font-semibold">{t("recordPayment")}</h2>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">{t("paymentAmount")}</label>
              <input
                type="number"
                min={0}
                max={remaining}
                step="0.01"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                className="w-40 rounded-md border bg-background px-3 py-2 text-sm"
                placeholder={String(remaining)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">{t("paymentMethod")}</label>
              <Select value={payMethod} onValueChange={setPayMethod}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CASH">{t("cash")}</SelectItem>
                  <SelectItem value="CARD">{t("card")}</SelectItem>
                  <SelectItem value="BANK_TRANSFER">{t("bankTransfer")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handlePay} disabled={payMut.isPending || !payAmount}>
              {t("recordPayment")}
            </Button>
            <Button variant="outline" onClick={handlePayFull} disabled={payMut.isPending}>
              {t("payFull")}
            </Button>
          </div>
          {payMut.isError && (
            <p className="mt-2 text-sm text-red-600">{t("paymentFailed")}</p>
          )}
          {payMut.isSuccess && (
            <p className="mt-2 text-sm text-green-600">{t("paymentSuccess")}</p>
          )}
        </div>
      )}

      {/* Payment History */}
      <h2 className="mb-3 text-lg font-semibold">{t("paymentHistory")}</h2>
      {data.payments.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noPayments")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("paymentDate")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("amount")}</th>
              </tr>
            </thead>
            <tbody>
              {data.payments.map((p) => (
                <tr key={p.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2.5">{fmtDate(p.payment_date, locale)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(p.amount)} SAR</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
