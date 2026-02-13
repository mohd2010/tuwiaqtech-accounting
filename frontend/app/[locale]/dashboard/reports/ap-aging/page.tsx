"use client";

import { useState } from "react";
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import ExportButton from "@/components/reports/ExportButton";

interface AgingBucketRow {
  name: string;
  current: string;
  days_31_60: string;
  days_61_90: string;
  over_90: string;
  total: string;
}

interface APAgingData {
  as_of_date: string;
  kpi: {
    total_payable: string;
    total_overdue: string;
  };
  suppliers: AgingBucketRow[];
  totals: AgingBucketRow;
}

export default function APAgingPage() {
  const t = useTranslations("apAging");
  const tFilters = useTranslations("reportFilters");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);

  const [asOfDate, setAsOfDate] = useState(() => new Date());
  const [calOpen, setCalOpen] = useState(false);
  const dateStr = format(asOfDate, "yyyy-MM-dd");

  const { data, isLoading } = useQuery<APAgingData>({
    queryKey: ["ap-aging", dateStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/ap-aging", {
          params: { as_of_date: dateStr },
        })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  const totalOverdue = Number(data.kpi.total_overdue);

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">{dateStr}</p>

      {/* As of date picker */}
      <div className="mb-6 flex items-center gap-3">
        <span className="text-sm font-medium">{tFilters("asOfDate")}:</span>
        <Popover open={calOpen} onOpenChange={setCalOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-[160px] justify-start text-left font-normal">
              <CalendarIcon className="ltr:mr-2 rtl:ml-2 size-4" />
              {dateStr}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="single"
              selected={asOfDate}
              onSelect={(d) => {
                if (d) {
                  setAsOfDate(d);
                  setCalOpen(false);
                }
              }}
              initialFocus
            />
          </PopoverContent>
        </Popover>
        <ExportButton
          baseUrl="/api/v1/reports/ap-aging"
          params={{ as_of_date: dateStr }}
          locale={locale}
        />
      </div>

      {/* KPI Cards */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalPayable")}
          </p>
          <p className="mt-1 text-2xl font-bold">{fmt(data.kpi.total_payable)} SAR</p>
        </div>
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalOverdue")}
          </p>
          <p className={cn("mt-1 text-2xl font-bold", totalOverdue > 0 && "text-red-600")}>
            {fmt(data.kpi.total_overdue)} SAR
          </p>
        </div>
      </div>

      {/* Aging Table */}
      {data.suppliers.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noData")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("supplier")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("current")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("days31_60")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("days61_90")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("over90")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("total")}</th>
              </tr>
            </thead>
            <tbody>
              {data.suppliers.map((row) => (
                <tr key={row.name} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-medium">{row.name}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(row.current)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(row.days_31_60)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(row.days_61_90)}</td>
                  <td className={cn("px-4 py-2.5 text-right tabular-nums", Number(row.over_90) > 0 && "text-red-600 font-semibold")}>
                    {fmt(row.over_90)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">{fmt(row.total)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-foreground bg-muted/30 font-bold">
                <td className="px-4 py-3">{data.totals.name}</td>
                <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.current)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.days_31_60)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.days_61_90)}</td>
                <td className={cn("px-4 py-3 text-right tabular-nums", Number(data.totals.over_90) > 0 && "text-red-600")}>
                  {fmt(data.totals.over_90)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
