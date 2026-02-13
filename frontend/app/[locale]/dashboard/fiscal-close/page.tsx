"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Lock, Plus } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

interface FiscalCloseRow {
  id: string;
  fiscal_year: number;
  close_date: string;
  closing_entry_id: string;
  closed_by: string;
  closed_at: string;
  notes: string | null;
}

export default function FiscalClosePage() {
  const t = useTranslations("fiscalClose");
  const tc = useTranslations("common");
  const qc = useQueryClient();

  const { data: closes, isLoading } = useQuery<FiscalCloseRow[]>({
    queryKey: ["fiscal-close"],
    queryFn: () => api.get("/api/v1/fiscal-close").then((r) => r.data),
  });

  // ── Close year dialog ──
  const [dialogOpen, setDialogOpen] = useState(false);
  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState(currentYear - 1);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const closeMutation = useMutation({
    mutationFn: (body: { fiscal_year: number; notes?: string }) =>
      api.post("/api/v1/fiscal-close", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fiscal-close"] });
      setDialogOpen(false);
      setNotes("");
      setError("");
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? t("closeFailed");
      setError(msg);
    },
  });

  // Build year options: from currentYear-1 down to 2020
  const yearOptions: number[] = [];
  for (let y = currentYear - 1; y >= 2020; y--) {
    yearOptions.push(y);
  }

  // Already-closed years
  const closedYears = new Set(closes?.map((c) => c.fiscal_year) ?? []);

  if (isLoading) {
    return <p className="text-muted-foreground">{t("loading")}</p>;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <Button
          onClick={() => {
            setError("");
            setDialogOpen(true);
          }}
        >
          <Lock className="size-4" />
          {t("closeFiscalYear")}
        </Button>
      </div>

      {!closes || closes.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noCloses")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">
                  {t("fiscalYear")}
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  {t("closeDate")}
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  {t("closedAt")}
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  {t("status")}
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  {t("notes")}
                </th>
              </tr>
            </thead>
            <tbody>
              {closes.map((fc) => (
                <tr
                  key={fc.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-4 py-2.5 font-medium">{fc.fiscal_year}</td>
                  <td className="px-4 py-2.5">{fc.close_date}</td>
                  <td className="px-4 py-2.5">
                    {fc.closed_at
                      ? new Date(fc.closed_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="inline-block rounded bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700 dark:bg-green-900/40 dark:text-green-300">
                      {t("closed")}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {fc.notes || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Close Fiscal Year Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("closeFiscalYear")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("fiscalYear")}
              </label>
              <select
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y} disabled={closedYears.has(y)}>
                    {y} {closedYears.has(y) ? `(${t("closed")})` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("notes")}
              </label>
              <textarea
                className="flex w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                rows={3}
                placeholder={t("notesPlaceholder")}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            {/* Confirmation warning */}
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200">
              {t("confirmClose", { year: selectedYear })}
            </div>

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200">
                {error}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={closeMutation.isPending || closedYears.has(selectedYear)}
              onClick={() =>
                closeMutation.mutate({
                  fiscal_year: selectedYear,
                  notes: notes || undefined,
                })
              }
            >
              {closeMutation.isPending ? t("closing") : t("confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
