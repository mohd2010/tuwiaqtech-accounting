"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  ChevronDown,
  ChevronRight,
  Search,
  SlidersHorizontal,
  Eye,
  Printer,
  MoreHorizontal,
  Plus,
  ChevronLeft,
} from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate } from "@/lib/format";

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

interface PaginatedResponse {
  items: JournalEntry[];
  total: number;
}

interface Account {
  id: string;
  code: string;
  name: string;
  account_type: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function deriveTransactionType(description: string): string {
  const d = description.toLowerCase();
  if (d.includes("pos sale") || d.includes("pos sell")) return "POS Sell";
  if (d.includes("pos return") || d.includes("return")) return "Return";
  if (d.includes("purchase order") || d.includes("po received")) return "Purchase";
  if (d.includes("expense")) return "Expense";
  if (d.includes("stock adjustment") || d.includes("adjustment")) return "Adjustment";
  if (d.includes("transfer")) return "Transfer";
  if (d.includes("supplier payment")) return "Payment";
  if (d.includes("fiscal close") || d.includes("closing")) return "Fiscal Close";
  return "Journal";
}

function deriveLocation(description: string): string {
  if (description.toLowerCase().includes("pos")) return "Main";
  return "—";
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function JournalPage() {
  const t = useTranslations("journalPage");
  const tData = useTranslations("FinancialData");
  const tc = useTranslations("common");
  const locale = useLocale();

  const fmt = (v: string | number) => fmtNumber(v, locale, { zeroBlank: true });

  // State
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Debounce search
  const [debounceTimer, setDebounceTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearch(value);
      if (debounceTimer) clearTimeout(debounceTimer);
      const timer = setTimeout(() => {
        setDebouncedSearch(value);
        setPage(1);
      }, 300);
      setDebounceTimer(timer);
    },
    [debounceTimer],
  );

  // Queries
  const { data, isLoading } = useQuery<PaginatedResponse>({
    queryKey: ["journal-entries", page, pageSize, debouncedSearch, sort],
    queryFn: () =>
      api
        .get("/api/v1/journal/entries", {
          params: { page, page_size: pageSize, search: debouncedSearch, sort },
        })
        .then((r) => r.data),
  });

  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/journal/accounts").then((r) => r.data),
  });

  const entries = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const showingFrom = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const showingTo = Math.min(page * pageSize, total);

  const accountMap = Object.fromEntries(
    accounts.map((a) => [a.id, `${a.code} - ${tData.has(a.name) ? tData(a.name) : a.name}`]),
  );

  // Compute entry numbers (descending: total, total-1, ...)
  const entryNumberBase = sort === "newest" ? total - (page - 1) * pageSize : (page - 1) * pageSize + 1;

  // Pagination helpers
  const getPageNumbers = (): (number | "...")[] => {
    const pages: (number | "...")[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (page > 3) pages.push("...");
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
        pages.push(i);
      }
      if (page < totalPages - 2) pages.push("...");
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <button className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 transition-colors">
          <Plus className="size-4" />
          {t("newJournalEntry")}
        </button>
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[260px]">
          <Search className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full rounded-lg border bg-background py-2.5 ps-10 pe-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
          />
        </div>

        {/* Filters button */}
        <button className="inline-flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted/50 transition-colors">
          <SlidersHorizontal className="size-4" />
          {t("filters")}
        </button>

        {/* Sort dropdown */}
        <select
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as "newest" | "oldest");
            setPage(1);
          }}
          className="rounded-lg border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
        >
          <option value="newest">{t("newestFirst")}</option>
          <option value="oldest">{t("oldestFirst")}</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-start font-medium">{t("entryNumber")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("date")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("status")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("transactionType")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("referenceNumber")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("location")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("notes")}</th>
                <th className="px-4 py-3 text-end font-medium">{t("totalCol")}</th>
                <th className="px-4 py-3 text-center font-medium">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                    {tc("loading")}
                  </td>
                </tr>
              ) : entries.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                    {t("noEntries")}
                  </td>
                </tr>
              ) : (
                entries.map((entry, idx) => {
                  const entryNum =
                    sort === "newest"
                      ? entryNumberBase - idx
                      : entryNumberBase + idx;
                  const isExpanded = expandedId === entry.id;

                  const totalDebit = entry.splits.reduce(
                    (sum, s) => sum + Number(s.debit_amount),
                    0,
                  );

                  return (
                    <JournalRow
                      key={entry.id}
                      entry={entry}
                      entryNum={entryNum}
                      isExpanded={isExpanded}
                      onToggle={() =>
                        setExpandedId(isExpanded ? null : entry.id)
                      }
                      accountMap={accountMap}
                      locale={locale}
                      fmt={fmt}
                      t={t}
                      totalDebit={totalDebit}
                    />
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination footer */}
      {total > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          {/* Page size selector */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{t("noOfResults")}</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="rounded-md border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>

          {/* Info + page buttons */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {t("showing")} {showingFrom}-{showingTo} {t("of")} {total}
            </span>

            <div className="flex items-center gap-1">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="inline-flex size-8 items-center justify-center rounded-md border text-sm disabled:opacity-40 hover:bg-muted/50 transition-colors"
              >
                <ChevronLeft className="size-4" />
              </button>

              {getPageNumbers().map((p, i) =>
                p === "..." ? (
                  <span key={`ellipsis-${i}`} className="px-1 text-muted-foreground">
                    ...
                  </span>
                ) : (
                  <button
                    key={p}
                    onClick={() => setPage(p as number)}
                    className={cn(
                      "inline-flex size-8 items-center justify-center rounded-md text-sm transition-colors",
                      p === page
                        ? "bg-teal-600 text-white"
                        : "border hover:bg-muted/50",
                    )}
                  >
                    {p}
                  </button>
                ),
              )}

              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex size-8 items-center justify-center rounded-md border text-sm disabled:opacity-40 hover:bg-muted/50 transition-colors"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Expandable Row ──────────────────────────────────────────────────────────

function JournalRow({
  entry,
  entryNum,
  isExpanded,
  onToggle,
  accountMap,
  locale,
  fmt,
  t,
  totalDebit,
}: {
  entry: JournalEntry;
  entryNum: number;
  isExpanded: boolean;
  onToggle: () => void;
  accountMap: Record<string, string>;
  locale: string;
  fmt: (v: string | number) => string;
  t: (key: string) => string;
  totalDebit: number;
}) {
  const transactionType = deriveTransactionType(entry.description);
  const location = deriveLocation(entry.description);

  return (
    <>
      {/* Header row */}
      <tr className="border-b hover:bg-muted/30 transition-colors">
        {/* Entry Number */}
        <td className="px-4 py-3">
          <button
            onClick={onToggle}
            className="inline-flex items-center gap-1.5 font-medium text-teal-600 hover:text-teal-700 hover:underline"
          >
            {isExpanded ? (
              <ChevronDown className="size-4 shrink-0" />
            ) : (
              <ChevronRight className="size-4 shrink-0" />
            )}
            #{entryNum}
          </button>
        </td>

        {/* Date */}
        <td className="px-4 py-3 whitespace-nowrap">
          {fmtDate(entry.entry_date, locale)}
        </td>

        {/* Status */}
        <td className="px-4 py-3">
          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            {t("posted")}
          </span>
        </td>

        {/* Transaction Type */}
        <td className="px-4 py-3 whitespace-nowrap">{transactionType}</td>

        {/* Reference Number */}
        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
          {entry.reference ?? "—"}
        </td>

        {/* Location */}
        <td className="px-4 py-3 whitespace-nowrap">{location}</td>

        {/* Notes */}
        <td className="px-4 py-3 max-w-[200px] truncate" title={entry.description}>
          {entry.description}
        </td>

        {/* Total */}
        <td className="px-4 py-3 text-end font-semibold tabular-nums text-teal-600">
          {fmt(totalDebit)}
        </td>

        {/* Actions */}
        <td className="px-4 py-3">
          <div className="flex items-center justify-center gap-1">
            <button
              onClick={onToggle}
              className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
              title={t("view")}
            >
              <Eye className="size-4" />
            </button>
            <button
              className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
              title={t("print")}
            >
              <Printer className="size-4" />
            </button>
            <button
              className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
            >
              <MoreHorizontal className="size-4" />
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded splits */}
      {isExpanded && (
        <tr className="border-b bg-muted/20">
          <td colSpan={9} className="px-0 py-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="px-10 py-2 text-start font-medium">{t("account")}</th>
                  <th className="px-4 py-2 text-end font-medium">{t("debit")}</th>
                  <th className="px-4 py-2 text-end font-medium">{t("credit")}</th>
                </tr>
              </thead>
              <tbody>
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
                        <td className="px-4 py-1.5 text-end tabular-nums">
                          {fmt(s.debit_amount)}
                        </td>
                        <td className="px-4 py-1.5 text-end tabular-nums">
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
