"use client";

import { useState } from "react";
import { startOfMonth, format } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { fmtNumber } from "@/lib/format";
import DateRangePicker from "@/components/reports/DateRangePicker";
import ExportButton from "@/components/reports/ExportButton";

interface MonthlyBreakdown {
  month: string;
  vat_collected: string;
  sales_ex_vat: string;
  transaction_count: number;
}

interface VATData {
  from_date: string;
  to_date: string;
  total_vat_collected: string;
  total_sales_ex_vat: string;
  effective_vat_rate: string;
  monthly_breakdown: MonthlyBreakdown[];
}

export default function VATReportPage() {
  const t = useTranslations("vatReport");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);

  const [fromDate, setFromDate] = useState(() => startOfMonth(new Date()));
  const [toDate, setToDate] = useState(() => new Date());

  const fromStr = format(fromDate, "yyyy-MM-dd");
  const toStr = format(toDate, "yyyy-MM-dd");

  const { data, isLoading } = useQuery<VATData>({
    queryKey: ["vat-report", fromStr, toStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/vat-report", {
          params: { from_date: fromStr, to_date: toStr },
        })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        {fromStr} — {toStr}
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
          baseUrl="/api/v1/reports/vat-report"
          params={{ from_date: fromStr, to_date: toStr }}
          locale={locale}
        />
      </div>

      {/* KPI Cards */}
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalVatCollected")}
          </p>
          <p className="mt-1 text-2xl font-bold">{fmt(data.total_vat_collected)} SAR</p>
        </div>
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalSalesExVat")}
          </p>
          <p className="mt-1 text-2xl font-bold">{fmt(data.total_sales_ex_vat)} SAR</p>
        </div>
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("effectiveVatRate")}
          </p>
          <p className="mt-1 text-2xl font-bold">{data.effective_vat_rate}%</p>
        </div>
      </div>

      {/* Monthly Breakdown */}
      <h2 className="mb-3 text-lg font-semibold">{t("monthlyBreakdown")}</h2>

      {data.monthly_breakdown.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noData")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("month")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("vatCollected")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("salesExVat")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("transactions")}</th>
              </tr>
            </thead>
            <tbody>
              {data.monthly_breakdown.map((m) => (
                <tr key={m.month} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-medium">{m.month}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(m.vat_collected)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(m.sales_ex_vat)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{m.transaction_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
