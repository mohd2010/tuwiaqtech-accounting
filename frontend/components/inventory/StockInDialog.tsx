"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";

interface Account {
  id: string;
  code: string;
  name: string;
  account_type: string;
}

const stockInSchema = z.object({
  quantity: z.number().int().min(1, "Must be at least 1"),
  total_cost: z.number().min(0.01, "Must be > 0"),
  payment_account_id: z.string().min(1, "Select an account"),
});

type StockInForm = z.infer<typeof stockInSchema>;

export function StockInDialog({
  productId,
  productName,
  onClose,
  onSuccess,
}: {
  productId: string;
  productName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const t = useTranslations("stockIn");
  const tc = useTranslations("common");
  const tf = useTranslations("FinancialData");
  const [apiError, setApiError] = useState("");

  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/journal/accounts").then((r) => r.data),
  });

  // Only show Cash and Bank as payment sources
  const paymentAccounts = accounts.filter(
    (a) => a.account_type === "ASSET" && a.code !== "1100",
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<StockInForm>({
    resolver: zodResolver(stockInSchema),
  });

  const mutation = useMutation({
    mutationFn: (data: StockInForm) =>
      api.post(`/api/v1/inventory/products/${productId}/stock-in`, data),
    onSuccess,
    onError: () => setApiError(t("failedToAdd")),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg border bg-card p-6 shadow-lg">
        <h2 className="mb-1 text-lg font-semibold">{t("title")}</h2>
        <p className="mb-4 text-sm text-muted-foreground">{productName}</p>

        <form
          onSubmit={handleSubmit((data) => mutation.mutate(data))}
          className="space-y-3"
        >
          <div>
            <label className="mb-1 block text-sm font-medium">{t("quantity")}</label>
            <input
              type="number"
              {...register("quantity", { valueAsNumber: true })}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            {errors.quantity && (
              <p className="mt-1 text-xs text-red-500">
                {errors.quantity.message}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">
              {t("totalCost")}
            </label>
            <input
              type="number"
              step="0.01"
              {...register("total_cost", { valueAsNumber: true })}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            {errors.total_cost && (
              <p className="mt-1 text-xs text-red-500">
                {errors.total_cost.message}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">
              {t("payFromAccount")}
            </label>
            <select
              {...register("payment_account_id")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">{tc("select")}</option>
              {paymentAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {tf.has(a.name) ? tf(a.name) : a.name} — {a.code}
                </option>
              ))}
            </select>
            {errors.payment_account_id && (
              <p className="mt-1 text-xs text-red-500">
                {errors.payment_account_id.message}
              </p>
            )}
          </div>

          {apiError && (
            <p className="text-center text-sm text-red-500">{apiError}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {tc("cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? tc("loading") : t("confirmStockIn")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
