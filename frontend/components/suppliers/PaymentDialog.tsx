"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { fmtNumber } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Account {
  id: string;
  code: string;
  name: string;
  account_type: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function PaymentDialog({
  supplierId,
  supplierName,
  onClose,
  onSuccess,
}: {
  supplierId: string;
  supplierName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const t = useTranslations("payment");
  const tc = useTranslations("common");
  const tf = useTranslations("FinancialData");
  const locale = useLocale();
  const fmt = (v: string | number) => fmtNumber(v, locale);

  const [amount, setAmount] = useState("");
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [error, setError] = useState("");

  // Fetch outstanding balance
  const { data: balanceData, isLoading: balanceLoading } = useQuery<{
    balance: string;
  }>({
    queryKey: ["supplier-balance", supplierId],
    queryFn: () =>
      api.get(`/api/v1/suppliers/${supplierId}/balance`).then((r) => r.data),
  });

  // Fetch payment accounts (Cash / Bank — asset accounts)
  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/journal/accounts").then((r) => r.data),
  });

  const paymentAccounts = accounts.filter(
    (a) =>
      a.account_type === "ASSET" &&
      ["1000", "1200"].includes(a.code),
  );

  const balance = Number(balanceData?.balance ?? 0);

  const mutation = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/suppliers/${supplierId}/pay`, {
        amount: parseFloat(amount),
        payment_account_id: paymentAccountId,
      }),
    onSuccess,
    onError: () => setError(t("paymentFailed")),
  });

  const parsedAmount = parseFloat(amount) || 0;
  const canSubmit =
    paymentAccountId !== "" && parsedAmount > 0;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mutation.mutate();
          }}
          className="space-y-4"
        >
          {/* Supplier info */}
          <div className="rounded-md border bg-muted/30 px-4 py-3">
            <p className="text-sm font-medium">{supplierName}</p>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-xs text-muted-foreground">
                {t("outstandingBalance")}
              </span>
              {balanceLoading ? (
                <span className="text-sm text-muted-foreground">{tc("loading")}</span>
              ) : (
                <span className="text-lg font-bold tabular-nums">
                  {fmt(balance)} SAR
                </span>
              )}
            </div>
          </div>

          {/* Payment amount */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t("paymentAmount")}
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            {balance > 0 && (
              <button
                type="button"
                onClick={() => setAmount(balance.toFixed(2))}
                className="mt-1 text-xs text-primary hover:underline"
              >
                {t("payFullBalance", { amount: fmt(balance) })}
              </button>
            )}
          </div>

          {/* Payment account */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t("payFrom")}
            </label>
            <select
              required
              value={paymentAccountId}
              onChange={(e) => setPaymentAccountId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">{t("selectAccount")}</option>
              {paymentAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {tf.has(a.name) ? tf(a.name) : a.name} — {a.code}
                </option>
              ))}
            </select>
          </div>

          {/* Summary */}
          {parsedAmount > 0 && (
            <div className="rounded-md border border-dashed px-4 py-3 text-sm">
              <p className="text-muted-foreground">
                {t("journalNote")}
              </p>
              <p className="mt-1">
                <span className="font-medium">{t("debitLabel")}</span> {t("supplierPayables")}:{" "}
                <span className="font-semibold tabular-nums">
                  {fmt(parsedAmount)}
                </span>
              </p>
              <p>
                <span className="font-medium">{t("creditLabel")}</span>{" "}
                {paymentAccounts.find((a) => a.id === paymentAccountId)
                  ? `${tf.has(paymentAccounts.find((a) => a.id === paymentAccountId)!.name) ? tf(paymentAccounts.find((a) => a.id === paymentAccountId)!.name) : paymentAccounts.find((a) => a.id === paymentAccountId)!.name} — ${paymentAccounts.find((a) => a.id === paymentAccountId)!.code}`
                  : t("paymentAccount")}
                :{" "}
                <span className="font-semibold tabular-nums">
                  {fmt(parsedAmount)}
                </span>
              </p>
            </div>
          )}

          {error && (
            <p className="text-center text-sm text-red-500">{error}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {tc("cancel")}
            </Button>
            <Button type="submit" disabled={!canSubmit || mutation.isPending}>
              {mutation.isPending ? tc("loading") : t("recordPayment")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
