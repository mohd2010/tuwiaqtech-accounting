"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { ChevronDown, ChevronRight } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate, fmtTime } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Split {
  id: string;
  account_id: string;
  debit_amount: string;
  credit_amount: string;
}

interface JournalEntry {
  id: string;
  entry_date: string;
  description: string;
  reference: string | null;
  created_at: string;
  splits: Split[];
}

interface Account {
  id: string;
  code: string;
  name: string;
  account_type: string;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function JournalPage() {
  const t = useTranslations("journalPage");
  const tData = useTranslations("FinancialData");
  const tc = useTranslations("common");
  const locale = useLocale();

  const fmt = (v: string | number) => fmtNumber(v, locale, { zeroBlank: true });

  const { data: entries = [], isLoading } = useQuery<JournalEntry[]>({
    queryKey: ["journal-entries"],
    queryFn: () => api.get("/api/v1/journal/entries").then((r) => r.data),
  });

  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/journal/accounts").then((r) => r.data),
  });

  const accountMap = Object.fromEntries(
    accounts.map((a) => [a.id, `${a.code} - ${tData.has(a.name) ? tData(a.name) : a.name}`]),
  );

  // Already sorted newest-first from the API, but ensure it
  const sorted = [...entries].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <div>
      <h1 className="mb-6 text-3xl font-bold">{t("title")}</h1>

      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="w-8 px-2 py-3" />
              <th className="px-4 py-3 text-left font-medium">{t("date")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("description")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("ref")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("totalCol")}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  {tc("loading")}
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  {t("noEntries")}
                </td>
              </tr>
            ) : (
              sorted.map((entry) => (
                <JournalRow
                  key={entry.id}
                  entry={entry}
                  accountMap={accountMap}
                  locale={locale}
                  fmt={fmt}
                  t={t}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Expandable Row ──────────────────────────────────────────────────────────

function JournalRow({
  entry,
  accountMap,
  locale,
  fmt,
  t,
}: {
  entry: JournalEntry;
  accountMap: Record<string, string>;
  locale: string;
  fmt: (v: string | number) => string;
  t: (key: string) => string;
}) {
  const [open, setOpen] = useState(false);

  const totalDebit = entry.splits.reduce(
    (sum, s) => sum + Number(s.debit_amount),
    0,
  );

  return (
    <>
      {/* Header row */}
      <tr
        className="border-b cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <td className="px-2 py-3 text-center text-muted-foreground">
          {open ? (
            <ChevronDown className="inline size-4" />
          ) : (
            <ChevronRight className="inline size-4" />
          )}
        </td>
        <td className="px-4 py-3 whitespace-nowrap">
          <span>{fmtDate(entry.entry_date, locale)}</span>
          <span className="ltr:ml-2 rtl:mr-2 text-xs text-muted-foreground">
            {fmtTime(entry.created_at, locale)}
          </span>
        </td>
        <td className="px-4 py-3">{entry.description}</td>
        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
          {entry.reference ?? "—"}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {fmt(totalDebit)}
        </td>
      </tr>

      {/* Expanded splits */}
      {open && (
        <tr className="border-b bg-muted/20">
          <td colSpan={5} className="px-0 py-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="px-10 py-2 text-left font-medium">{t("account")}</th>
                  <th className="px-4 py-2 text-right font-medium">{t("debit")}</th>
                  <th className="px-4 py-2 text-right font-medium">{t("credit")}</th>
                </tr>
              </thead>
              <tbody>
                {/* Debits first, then credits */}
                {[...entry.splits]
                  .sort((a, b) => Number(b.debit_amount) - Number(a.debit_amount))
                  .map((s) => {
                    const isDebit = Number(s.debit_amount) > 0;
                    return (
                      <tr key={s.id} className="border-t border-dashed border-border/50">
                        <td
                          className={cn(
                            "px-10 py-1.5",
                            !isDebit && "ltr:pl-16 rtl:pr-16",
                          )}
                        >
                          {accountMap[s.account_id] ?? s.account_id}
                        </td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {fmt(s.debit_amount)}
                        </td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {fmt(s.credit_amount)}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}
