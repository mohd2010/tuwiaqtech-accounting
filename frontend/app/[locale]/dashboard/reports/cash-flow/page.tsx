"use client";

import { useState } from "react";
import { startOfMonth, format } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber } from "@/lib/format";
import DateRangePicker from "@/components/reports/DateRangePicker";
import ExportButton from "@/components/reports/ExportButton";

interface CashFlowLineItem {
  description: string;
  amount: string;
}

interface CashFlowSection {
  items: CashFlowLineItem[];
  total: string;
}

interface CashFlowData {
  from_date: string;
  to_date: string;
  opening_cash_balance: string;
  operating: CashFlowSection;
  investing: CashFlowSection;
  financing: CashFlowSection;
  net_change: string;
  closing_cash_balance: string;
}

export default function CashFlowPage() {
  const t = useTranslations("cashFlow");
  const tData = useTranslations("FinancialData");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);

  const [fromDate, setFromDate] = useState(() => startOfMonth(new Date()));
  const [toDate, setToDate] = useState(() => new Date());

  const fromStr = format(fromDate, "yyyy-MM-dd");
  const toStr = format(toDate, "yyyy-MM-dd");

  const { data, isLoading } = useQuery<CashFlowData>({
    queryKey: ["cash-flow", fromStr, toStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/cash-flow", {
          params: { from_date: fromStr, to_date: toStr },
        })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  const netChange = Number(data.net_change);

  return (
    <div className="mx-auto max-w-2xl">
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
          baseUrl="/api/v1/reports/cash-flow"
          params={{ from_date: fromStr, to_date: toStr }}
          locale={locale}
        />
      </div>

      <div className="rounded-lg border bg-card">
        {/* Opening Balance */}
        <div className="border-b bg-muted/20 px-6 py-3">
          <div className="flex justify-between text-sm font-semibold">
            <span>{t("openingBalance")}</span>
            <span className="tabular-nums">{fmt(data.opening_cash_balance)} SAR</span>
          </div>
        </div>

        {/* Operating */}
        <FlowSection
          title={t("operating")}
          section={data.operating}
          fmt={fmt}
          tData={tData}
          noActivityLabel={t("noActivity")}
          totalLabel={t("total")}
        />

        {/* Investing */}
        <FlowSection
          title={t("investing")}
          section={data.investing}
          fmt={fmt}
          tData={tData}
          noActivityLabel={t("noActivity")}
          totalLabel={t("total")}
        />

        {/* Financing */}
        <FlowSection
          title={t("financing")}
          section={data.financing}
          fmt={fmt}
          tData={tData}
          noActivityLabel={t("noActivity")}
          totalLabel={t("total")}
        />

        {/* Net Change */}
        <div className="border-t-2 border-foreground/20 px-6 py-3">
          <div className="flex justify-between text-base font-bold">
            <span>{t("netChange")}</span>
            <span
              className={cn(
                "tabular-nums",
                netChange > 0
                  ? "text-green-600"
                  : netChange < 0
                    ? "text-red-600"
                    : "",
              )}
            >
              {netChange < 0 ? `(${fmt(String(Math.abs(netChange)))})` : fmt(data.net_change)} SAR
            </span>
          </div>
        </div>

        {/* Closing Balance */}
        <div className="border-t-2 border-foreground bg-muted/30 px-6 py-4">
          <div className="flex justify-between text-lg font-extrabold">
            <span>{t("closingBalance")}</span>
            <span className="tabular-nums">{fmt(data.closing_cash_balance)} SAR</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function FlowSection({
  title,
  section,
  fmt,
  tData,
  noActivityLabel,
  totalLabel,
}: {
  title: string;
  section: CashFlowSection;
  fmt: (v: string) => string;
  tData: ReturnType<typeof useTranslations>;
  noActivityLabel: string;
  totalLabel: string;
}) {
  return (
    <div className="border-b px-6 py-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {section.items.length === 0 ? (
        <p className="py-1 text-sm text-muted-foreground ltr:pl-4 rtl:pr-4">
          {noActivityLabel}
        </p>
      ) : (
        section.items.map((item, i) => (
          <div key={i} className="flex justify-between py-1 text-sm ltr:pl-4 rtl:pr-4">
            <span>{tData.has(item.description) ? tData(item.description) : item.description}</span>
            <span className="tabular-nums">{fmt(item.amount)}</span>
          </div>
        ))
      )}
      <div className="mt-1 flex justify-between border-t border-dashed pt-1 text-sm font-semibold">
        <span>{totalLabel}</span>
        <span className="tabular-nums">{fmt(section.total)}</span>
      </div>
    </div>
  );
}
