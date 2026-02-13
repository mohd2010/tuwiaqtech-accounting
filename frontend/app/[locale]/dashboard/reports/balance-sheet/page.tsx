"use client";

import { useState } from "react";
import { format } from "date-fns";
import { CalendarIcon, CheckCircle, AlertTriangle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import ExportButton from "@/components/reports/ExportButton";

// --- Types ---

interface AccountLine {
  code: string;
  name: string;
  balance: string;
}

interface BalanceSheetData {
  as_of_date: string;
  assets: AccountLine[];
  total_assets: string;
  liabilities: AccountLine[];
  total_liabilities: string;
  equity: AccountLine[];
  total_equity: string;
  retained_earnings: string;
  total_liabilities_and_equity: string;
  is_balanced: boolean;
}

// --- Page ---

export default function BalanceSheetPage() {
  const t = useTranslations("balanceSheet");
  const tFilters = useTranslations("reportFilters");
  const tData = useTranslations("FinancialData");
  const locale = useLocale();
  const fmt = (v: string) => {
    const n = Number(v);
    if (n === 0) return "\u2014";
    return fmtNumber(v, locale);
  };
  const fmtTotal = (v: string) => fmtNumber(v, locale);

  const [asOfDate, setAsOfDate] = useState(() => new Date());
  const [calOpen, setCalOpen] = useState(false);
  const dateStr = format(asOfDate, "yyyy-MM-dd");

  const { data, isLoading } = useQuery<BalanceSheetData>({
    queryKey: ["balance-sheet", dateStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/balance-sheet", {
          params: { as_of_date: dateStr },
        })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("asOfDate")} &middot; {dateStr}
      </p>

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
          baseUrl="/api/v1/reports/balance-sheet"
          params={{ as_of_date: dateStr }}
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
                Math.abs(
                  Number(data.total_assets) -
                    Number(data.total_liabilities_and_equity),
                ),
              ),
            )}
          </span>
        )}
      </div>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Assets */}
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="border-b bg-muted/50 px-5 py-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t("assets")}
            </h2>
          </div>

          <div className="px-5 py-3">
            {data.assets.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                {t("noAssets")}
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground">
                    <th className="pb-2 text-left font-medium">{t("code")}</th>
                    <th className="pb-2 text-left font-medium">{t("account")}</th>
                    <th className="pb-2 text-right font-medium">{t("balance")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.assets.map((a) => (
                    <tr
                      key={a.code}
                      className="border-t border-dashed border-border/50"
                    >
                      <td className="py-2 ltr:pr-3 rtl:pl-3 font-mono text-xs text-muted-foreground">
                        {a.code}
                      </td>
                      <td className="py-2">{tData.has(a.name) ? tData(a.name) : a.name}</td>
                      <td className="py-2 text-right tabular-nums">
                        {fmt(a.balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="border-t-2 border-foreground bg-muted/30 px-5 py-3">
            <div className="flex justify-between text-base font-bold">
              <span>{t("totalAssets")}</span>
              <span className="tabular-nums">
                {fmtTotal(data.total_assets)} SAR
              </span>
            </div>
          </div>
        </div>

        {/* Right: Liabilities + Equity */}
        <div className="overflow-hidden rounded-lg border bg-card">
          {/* Liabilities */}
          <div className="border-b bg-muted/50 px-5 py-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t("liabilities")}
            </h2>
          </div>

          <div className="px-5 py-3">
            {data.liabilities.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                {t("noLiabilities")}
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground">
                    <th className="pb-2 text-left font-medium">{t("code")}</th>
                    <th className="pb-2 text-left font-medium">{t("account")}</th>
                    <th className="pb-2 text-right font-medium">{t("balance")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.liabilities.map((a) => (
                    <tr
                      key={a.code}
                      className="border-t border-dashed border-border/50"
                    >
                      <td className="py-2 ltr:pr-3 rtl:pl-3 font-mono text-xs text-muted-foreground">
                        {a.code}
                      </td>
                      <td className="py-2">{tData.has(a.name) ? tData(a.name) : a.name}</td>
                      <td className="py-2 text-right tabular-nums">
                        {fmt(a.balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="border-t px-5 py-2">
            <div className="flex justify-between text-sm font-semibold">
              <span>{t("totalLiabilities")}</span>
              <span className="tabular-nums">
                {fmtTotal(data.total_liabilities)}
              </span>
            </div>
          </div>

          {/* Equity */}
          <div className="border-t bg-muted/50 px-5 py-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t("equity")}
            </h2>
          </div>

          <div className="px-5 py-3">
            <table className="w-full text-sm">
              <tbody>
                {data.equity.map((a) => (
                  <tr
                    key={a.code}
                    className="border-t border-dashed border-border/50 first:border-0"
                  >
                    <td className="py-2 ltr:pr-3 rtl:pl-3 font-mono text-xs text-muted-foreground">
                      {a.code}
                    </td>
                    <td className="py-2">{tData.has(a.name) ? tData(a.name) : a.name}</td>
                    <td className="py-2 text-right tabular-nums">
                      {fmt(a.balance)}
                    </td>
                  </tr>
                ))}
                <tr className="border-t border-dashed border-border/50">
                  <td className="py-2 ltr:pr-3 rtl:pl-3" />
                  <td className="py-2 italic text-muted-foreground">
                    {t("retainedEarnings")}
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {fmt(data.retained_earnings)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="border-t px-5 py-2">
            <div className="flex justify-between text-sm font-semibold">
              <span>{t("totalEquity")}</span>
              <span className="tabular-nums">
                {fmtTotal(
                  String(
                    Number(data.total_equity) +
                      Number(data.retained_earnings),
                  ),
                )}
              </span>
            </div>
          </div>

          {/* Grand total */}
          <div className="border-t-2 border-foreground bg-muted/30 px-5 py-3">
            <div className="flex justify-between text-base font-bold">
              <span>{t("totalLiabilitiesAndEquity")}</span>
              <span className="tabular-nums">
                {fmtTotal(data.total_liabilities_and_equity)} SAR
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
