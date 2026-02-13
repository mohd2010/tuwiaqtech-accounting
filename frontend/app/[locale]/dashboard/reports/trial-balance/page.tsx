"use client";

import { useState } from "react";
import { startOfMonth, format } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { CheckCircle, AlertTriangle } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber } from "@/lib/format";
import DateRangePicker from "@/components/reports/DateRangePicker";
import ExportButton from "@/components/reports/ExportButton";

interface TrialBalanceAccount {
  account_code: string;
  account_name: string;
  account_type: string;
  debit: string;
  credit: string;
}

interface TrialBalanceData {
  from_date: string;
  to_date: string;
  accounts: TrialBalanceAccount[];
  total_debit: string;
  total_credit: string;
  is_balanced: boolean;
}

export default function TrialBalancePage() {
  const t = useTranslations("trialBalance");
  const tData = useTranslations("FinancialData");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale, { zeroBlank: true });
  const fmtTotal = (v: string) => fmtNumber(v, locale);

  const [fromDate, setFromDate] = useState(() => startOfMonth(new Date()));
  const [toDate, setToDate] = useState(() => new Date());

  const fromStr = format(fromDate, "yyyy-MM-dd");
  const toStr = format(toDate, "yyyy-MM-dd");

  const { data, isLoading } = useQuery<TrialBalanceData>({
    queryKey: ["trial-balance", fromStr, toStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/trial-balance", {
          params: { from_date: fromStr, to_date: toStr },
        })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("periodToDate")} &middot; {fromStr} — {toStr}
      </p>

      <div className="mb-6 flex items-center gap-4">
        <DateRangePicker
          fromDate={fromDate}
          toDate={toDate}
          onChange={(f, t2) => {
            setFromDate(f);
            setToDate(t2);
          }}
        />
        <ExportButton
          baseUrl="/api/v1/reports/trial-balance"
          params={{ from_date: fromStr, to_date: toStr }}
          locale={locale}
        />
      </div>

      {/* Balance indicator */}
      <div
        className={cn(
          "mb-6 flex items-center gap-3 rounded-lg border-2 px-5 py-4",
          data.is_balanced
            ? "border-green-500 bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400"
            : "border-red-500 bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400",
        )}
      >
        {data.is_balanced ? (
          <CheckCircle className="size-6" />
        ) : (
          <AlertTriangle className="size-6" />
        )}
        <span className="text-lg font-bold">
          {data.is_balanced ? t("balanced") : t("outOfBalance")}
        </span>
        {!data.is_balanced && (
          <span className="ltr:ml-auto rtl:mr-auto text-sm font-medium">
            {t("difference")}:{" "}
            {fmtTotal(
              String(
                Math.abs(Number(data.total_debit) - Number(data.total_credit)),
              ),
            )}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("code")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("account")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("type")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("debit")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("credit")}</th>
            </tr>
          </thead>
          <tbody>
            {data.accounts.map((a) => (
              <tr
                key={a.account_code}
                className="border-b last:border-0 hover:bg-muted/30"
              >
                <td className="px-4 py-2.5 font-mono text-xs">
                  {a.account_code}
                </td>
                <td className="px-4 py-2.5">{tData.has(a.account_name) ? tData(a.account_name) : a.account_name}</td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">
                  {tData.has(a.account_type) ? tData(a.account_type) : a.account_type}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {fmt(a.debit)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {fmt(a.credit)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-foreground bg-muted/30 font-bold">
              <td colSpan={3} className="px-4 py-3">
                {t("totals")}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {fmtTotal(data.total_debit)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {fmtTotal(data.total_credit)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
