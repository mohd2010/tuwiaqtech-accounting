"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { Receipt, CheckCircle, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

interface AccountOption {
  id: string;
  code: string;
  name: string;
  account_type: string;
}

interface ExpenseEntry {
  id: string;
  reference: string;
  description: string;
  amount: string;
  expense_account_name: string;
  payment_account_name: string;
  date: string;
  created_by: string;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ExpensesPage() {
  const t = useTranslations("expenses");
  const tf = useTranslations("FinancialData");
  const locale = useLocale();
  const queryClient = useQueryClient();

  // Form state
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("");
  const [expenseAccountId, setExpenseAccountId] = useState("");
  const [paymentAccountId, setPaymentAccountId] = useState("");
  const [amount, setAmount] = useState("");

  // Toast
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Fetch accounts for dropdowns
  const { data: accounts = [] } = useQuery<AccountOption[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/journal/accounts").then((r) => r.data),
  });

  const expenseAccounts = accounts.filter((a) => a.account_type === "EXPENSE");
  const paymentAccounts = accounts.filter((a) => a.account_type === "ASSET");

  // Fetch expense list
  const { data: expenses = [], isLoading: loadingExpenses } = useQuery<
    ExpenseEntry[]
  >({
    queryKey: ["expenses"],
    queryFn: () => api.get("/api/v1/expenses").then((r) => r.data),
  });

  // Submit mutation
  const mutation = useMutation({
    mutationFn: async () => {
      const res = await api.post("/api/v1/expenses", {
        description,
        amount,
        expense_account_id: expenseAccountId,
        payment_account_id: paymentAccountId,
        date: date || undefined,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expenses"] });
      // Reset form
      setDescription("");
      setAmount("");
      setExpenseAccountId("");
      showToast(t("success"), "success");
    },
    onError: () => {
      showToast(t("failed"), "error");
    },
  });

  const canSubmit =
    description.trim() &&
    expenseAccountId &&
    paymentAccountId &&
    Number(amount) > 0 &&
    !mutation.isPending;

  return (
    <div className="flex h-full gap-6">
      {/* ── Left: Form ──────────────────────────────────────────────── */}
      <div className="w-96 shrink-0">
        <div className="rounded-lg border bg-card p-6">
          <div className="mb-5 flex items-center gap-2">
            <Receipt className="size-5 text-primary" />
            <h2 className="text-lg font-semibold">{t("recordExpense")}</h2>
          </div>

          <div className="space-y-4">
            {/* Date */}
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("date")}
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("description")}
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("descriptionPlaceholder")}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Category (Expense Account) */}
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("category")}
              </label>
              <select
                value={expenseAccountId}
                onChange={(e) => setExpenseAccountId(e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">{t("selectCategory")}</option>
                {expenseAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {tf.has(a.name) ? tf(a.name) : a.name} — {a.code}
                  </option>
                ))}
              </select>
            </div>

            {/* Paid From (Payment Account) */}
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("paidFrom")}
              </label>
              <select
                value={paymentAccountId}
                onChange={(e) => setPaymentAccountId(e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">{t("selectPayment")}</option>
                {paymentAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {tf.has(a.name) ? tf(a.name) : a.name} — {a.code}
                  </option>
                ))}
              </select>
            </div>

            {/* Amount */}
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("amount")}
              </label>
              <div className="relative">
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  className="h-10 w-full rounded-md border bg-background px-3 ltr:pr-14 rtl:pl-14 text-sm tabular-nums placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <span className="absolute top-1/2 ltr:right-3 rtl:left-3 -translate-y-1/2 text-xs text-muted-foreground">
                  SAR
                </span>
              </div>
            </div>

            {/* Submit */}
            <Button
              className="w-full"
              size="lg"
              disabled={!canSubmit}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? t("processing") : t("recordPayment")}
            </Button>
          </div>
        </div>
      </div>

      {/* ── Right: Expense Log ──────────────────────────────────────── */}
      <div className="flex-1">
        <h1 className="mb-4 text-3xl font-bold">{t("title")}</h1>

        <div className="rounded-lg border bg-card">
          <div className="border-b px-4 py-3">
            <h2 className="text-lg font-semibold">{t("recentExpenses")}</h2>
          </div>

          {loadingExpenses ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              {t("loading")}
            </p>
          ) : expenses.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              {t("noExpenses")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="px-4 py-3 text-left font-semibold">
                      {t("date")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold">
                      {t("ref")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold">
                      {t("description")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold">
                      {t("category")}
                    </th>
                    <th className="px-4 py-3 text-right font-semibold">
                      {t("amount")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold">
                      {t("user")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.map((exp) => (
                    <tr
                      key={exp.id}
                      className="border-b last:border-0 hover:bg-muted/50"
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        {fmtDate(exp.date, locale)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                        {exp.reference}
                      </td>
                      <td className="px-4 py-3">{exp.description}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {exp.expense_account_name}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-medium">
                        {fmtNumber(exp.amount, locale)} SAR
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {exp.created_by}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Toast ─────────────────────────────────────────────────────── */}
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
