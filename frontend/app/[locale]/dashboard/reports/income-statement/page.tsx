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

interface ExpenseItem {
  code: string;
  name: string;
  amount: string;
}

interface RevenueItem {
  code: string;
  name: string;
  amount: string;
}

interface IncomeStatement {
  from_date: string;
  to_date: string;
  revenue: string;
  revenue_detail: RevenueItem[];
  cogs: string;
  gross_profit: string;
  operating_expenses: string;
  expense_detail: ExpenseItem[];
  net_income: string;
}

export default function IncomeStatementPage() {
  const t = useTranslations("incomeStatement");
  const tData = useTranslations("FinancialData");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);

  const [fromDate, setFromDate] = useState(() => startOfMonth(new Date()));
  const [toDate, setToDate] = useState(() => new Date());

  const fromStr = format(fromDate, "yyyy-MM-dd");
  const toStr = format(toDate, "yyyy-MM-dd");

  const { data, isLoading } = useQuery<IncomeStatement>({
    queryKey: ["income-statement", fromStr, toStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/income-statement", {
          params: { from_date: fromStr, to_date: toStr },
        })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  const netIncome = Number(data.net_income);
  const cogsItems = data.expense_detail.filter((e) => e.code === "5000");
  const opexItems = data.expense_detail.filter((e) => e.code !== "5000");

  return (
    <div className="mx-auto max-w-2xl">
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
          baseUrl="/api/v1/reports/income-statement"
          params={{ from_date: fromStr, to_date: toStr }}
          locale={locale}
        />
      </div>

      <div className="rounded-lg border bg-card">
        {/* Revenue */}
        <Section title={t("revenue")}>
          {data.revenue_detail.map((r) => (
            <Row key={r.code} label={tData.has(r.name) ? tData(r.name) : r.name} amount={fmt(r.amount)} indent />
          ))}
          <TotalRow label={t("totalRevenue")} amount={fmt(data.revenue)} />
        </Section>

        {/* COGS */}
        <Section title={t("cogs")}>
          {cogsItems.map((e) => (
            <Row
              key={e.code}
              label={tData.has(e.name) ? tData(e.name) : e.name}
              amount={`(${fmt(e.amount)})`}
              indent
              negative
            />
          ))}
          <TotalRow label={t("totalCogs")} amount={`(${fmt(data.cogs)})`} />
        </Section>

        {/* Gross Profit */}
        <div className="border-t-2 border-foreground/20 px-6 py-3">
          <div className="flex justify-between text-base font-bold">
            <span>{t("grossProfit")}</span>
            <span>{fmt(data.gross_profit)}</span>
          </div>
        </div>

        {/* Operating Expenses */}
        <Section title={t("operatingExpenses")}>
          {opexItems.length === 0 ? (
            <Row label={t("none")} amount="0.00" indent />
          ) : (
            opexItems.map((e) => (
              <Row
                key={e.code}
                label={tData.has(e.name) ? tData(e.name) : e.name}
                amount={`(${fmt(e.amount)})`}
                indent
                negative
              />
            ))
          )}
          <TotalRow
            label={t("totalOpex")}
            amount={`(${fmt(data.operating_expenses)})`}
          />
        </Section>

        {/* Net Income */}
        <div className="border-t-2 border-foreground px-6 py-4 bg-muted/30">
          <div className="flex justify-between text-lg font-extrabold">
            <span>{t("netIncome")}</span>
            <span
              className={cn(
                netIncome >= 0 ? "text-green-600" : "text-red-600",
              )}
            >
              {netIncome < 0 ? `(${fmt(String(Math.abs(netIncome)))})` : fmt(data.net_income)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Helper components ---

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b px-6 py-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Row({
  label,
  amount,
  indent,
  negative,
}: {
  label: string;
  amount: string;
  indent?: boolean;
  negative?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex justify-between py-1 text-sm",
        indent && "ltr:pl-4 rtl:pr-4",
        negative && "text-muted-foreground",
      )}
    >
      <span>{label}</span>
      <span className="tabular-nums">{amount}</span>
    </div>
  );
}

function TotalRow({ label, amount }: { label: string; amount: string }) {
  return (
    <div className="mt-1 flex justify-between border-t border-dashed pt-1 text-sm font-semibold">
      <span>{label}</span>
      <span className="tabular-nums">{amount}</span>
    </div>
  );
}
