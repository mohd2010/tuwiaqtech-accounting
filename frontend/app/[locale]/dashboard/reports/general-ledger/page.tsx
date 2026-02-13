"use client";

import { useState } from "react";
import { startOfMonth, format } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { fmtNumber, fmtDate } from "@/lib/format";
import DateRangePicker from "@/components/reports/DateRangePicker";
import ExportButton from "@/components/reports/ExportButton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AccountOption {
  id: string;
  code: string;
  name: string;
}

interface GLEntry {
  date: string;
  reference: string | null;
  description: string;
  debit: string;
  credit: string;
  running_balance: string;
}

interface GLData {
  account_code: string;
  account_name: string;
  from_date: string;
  to_date: string;
  opening_balance: string;
  entries: GLEntry[];
  closing_balance: string;
}

export default function GeneralLedgerPage() {
  const t = useTranslations("generalLedger");
  const tData = useTranslations("FinancialData");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);
  const fmtZ = (v: string) => fmtNumber(v, locale, { zeroBlank: true });

  const [fromDate, setFromDate] = useState(() => startOfMonth(new Date()));
  const [toDate, setToDate] = useState(() => new Date());
  const [accountCode, setAccountCode] = useState<string>("");

  const fromStr = format(fromDate, "yyyy-MM-dd");
  const toStr = format(toDate, "yyyy-MM-dd");

  // Fetch account list
  const { data: accounts } = useQuery<AccountOption[]>({
    queryKey: ["accounts-list"],
    queryFn: () => api.get("/api/v1/accounts").then((r) => r.data),
  });

  // Fetch GL data
  const { data, isLoading } = useQuery<GLData>({
    queryKey: ["general-ledger", accountCode, fromStr, toStr],
    queryFn: () =>
      api
        .get("/api/v1/reports/general-ledger", {
          params: { account_code: accountCode, from_date: fromStr, to_date: toStr },
        })
        .then((r) => r.data),
    enabled: !!accountCode,
  });

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        {data ? `${data.account_code} — ${tData.has(data.account_name) ? tData(data.account_name) : data.account_name}` : t("selectAccount")}
      </p>

      {/* Account selector */}
      <div className="mb-4 flex items-center gap-3">
        <Select value={accountCode} onValueChange={setAccountCode}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder={t("selectAccount")} />
          </SelectTrigger>
          <SelectContent>
            {accounts?.map((a) => (
              <SelectItem key={a.code} value={a.code}>
                {a.code} — {tData.has(a.name) ? tData(a.name) : a.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mb-6 flex items-center gap-4">
        <DateRangePicker
          fromDate={fromDate}
          toDate={toDate}
          onChange={(f, t2) => {
            setFromDate(f);
            setToDate(t2);
          }}
        />
        {accountCode && (
          <ExportButton
            baseUrl="/api/v1/reports/general-ledger"
            params={{ account_code: accountCode, from_date: fromStr, to_date: toStr }}
            locale={locale}
          />
        )}
      </div>

      {!accountCode && (
        <p className="mt-8 text-center text-muted-foreground">{t("selectAccount")}</p>
      )}

      {accountCode && isLoading && (
        <p className="text-muted-foreground">{t("loadingReport")}</p>
      )}

      {data && (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("date")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("reference")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("description")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("debit")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("credit")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("balance")}</th>
              </tr>
            </thead>
            <tbody>
              {/* Opening balance row */}
              <tr className="border-b border-dashed bg-muted/20 font-semibold">
                <td colSpan={5} className="px-4 py-2.5">
                  {t("openingBalance")}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {fmt(data.opening_balance)}
                </td>
              </tr>

              {data.entries.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    {t("noTransactions")}
                  </td>
                </tr>
              ) : (
                data.entries.map((e, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-2.5 text-xs">{fmtDate(e.date, locale)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {e.reference || "\u2014"}
                    </td>
                    <td className="px-4 py-2.5">{e.description}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmtZ(e.debit)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmtZ(e.credit)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                      {fmt(e.running_balance)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-foreground bg-muted/30 font-bold">
                <td colSpan={5} className="px-4 py-3">
                  {t("closingBalance")}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {fmt(data.closing_balance)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
