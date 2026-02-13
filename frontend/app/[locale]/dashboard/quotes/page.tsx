"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { FileCheck, Plus, Search, Eye } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

interface QuoteRow {
  id: string;
  quote_number: string;
  customer_name: string;
  status: string;
  expiry_date: string;
  total_amount: string;
  item_count: number;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700 dark:bg-gray-800/40 dark:text-gray-300",
  SENT: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  ACCEPTED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  REJECTED: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  CONVERTED: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
};

// ─── Page ────────────────────────────────────────────────────────────────────

export default function QuotesListPage() {
  const t = useTranslations("quotes");
  const locale = useLocale();
  const [search, setSearch] = useState("");

  const { data: quotes = [], isLoading } = useQuery<QuoteRow[]>({
    queryKey: ["quotes"],
    queryFn: () => api.get("/api/v1/quotes").then((r) => r.data),
  });

  const filtered = search.trim()
    ? quotes.filter(
        (q) =>
          q.quote_number.toLowerCase().includes(search.toLowerCase()) ||
          q.customer_name.toLowerCase().includes(search.toLowerCase()),
      )
    : quotes;

  const statusLabel = (s: string) => {
    const map: Record<string, string> = {
      DRAFT: t("draft"),
      SENT: t("sent"),
      ACCEPTED: t("accepted"),
      REJECTED: t("rejected"),
      CONVERTED: t("converted"),
    };
    return map[s] ?? s;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileCheck className="size-7 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        <Link href="/dashboard/quotes/create">
          <Button>
            <Plus className="size-4 ltr:mr-1 rtl:ml-1" />
            {t("newQuote")}
          </Button>
        </Link>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute top-1/2 ltr:left-3 rtl:right-3 -translate-y-1/2 size-4 text-muted-foreground" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("search")}
          className="h-10 w-full rounded-md border bg-background ltr:pl-10 ltr:pr-3 rtl:pr-10 rtl:pl-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Table */}
      <div className="rounded-lg border bg-card">
        {isLoading ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {t("loading")}
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {t("noQuotes")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("quoteNumber")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("customer")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("date")}</th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("expiry")}</th>
                  <th className="px-4 py-3 text-center font-semibold">{t("items")}</th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("amount")}</th>
                  <th className="px-4 py-3 text-center font-semibold">{t("status")}</th>
                  <th className="px-4 py-3 text-center font-semibold">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((q) => (
                  <tr key={q.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="px-4 py-3 font-mono text-xs font-medium">{q.quote_number}</td>
                    <td className="px-4 py-3">{q.customer_name}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmtDate(q.created_at, locale)}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmtDate(q.expiry_date, locale)}</td>
                    <td className="px-4 py-3 text-center tabular-nums">{q.item_count}</td>
                    <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums font-medium">
                      {fmtNumber(q.total_amount, locale)} SAR
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          STATUS_COLORS[q.status] ?? "",
                        )}
                      >
                        {statusLabel(q.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Link href={`/dashboard/quotes/${q.id}` as "/dashboard/quotes"}>
                        <Button variant="ghost" size="sm" className="h-8 px-2" title={t("view")}>
                          <Eye className="size-4" />
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
