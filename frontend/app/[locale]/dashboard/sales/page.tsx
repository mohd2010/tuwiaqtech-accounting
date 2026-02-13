"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { ScrollText, Printer, RotateCcw, Search } from "lucide-react";
import api from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate, fmtTime } from "@/lib/format";
import InvoiceModal, { type InvoiceData } from "@/components/pos/InvoiceModal";

// ─── Types ───────────────────────────────────────────────────────────────────

interface SaleRow {
  id: string;
  invoice_number: string;
  date: string;
  customer_name: string | null;
  cashier: string;
  item_count: number;
  total_amount: string;
  net_amount: string;
  vat_amount: string;
  status: "PAID" | "RETURNED";
  discount_amount: string;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function SalesHistoryPage() {
  const t = useTranslations("salesHistory");
  const locale = useLocale();
  const router = useRouter();
  const { toast } = useToast();

  const [search, setSearch] = useState("");
  const [receiptData, setReceiptData] = useState<InvoiceData | null>(null);

  // Fetch sales list
  const { data: sales = [], isLoading } = useQuery<SaleRow[]>({
    queryKey: ["sales"],
    queryFn: () => api.get("/api/v1/sales").then((r) => r.data),
  });

  // Filter by search
  const filtered = search.trim()
    ? sales.filter((s) =>
        s.invoice_number.toLowerCase().includes(search.toLowerCase()),
      )
    : sales;

  // Reprint handler: fetch full invoice detail and show modal
  const handleReprint = async (invoiceNumber: string) => {
    try {
      const res = await api.get(`/api/v1/sales/${invoiceNumber}`);
      setReceiptData(res.data);
    } catch {
      toast({ title: t("reprintError"), variant: "error" });
    }
  };

  // Navigate to returns page with invoice pre-filled
  const handleIssueReturn = (invoiceNumber: string) => {
    router.push(`/dashboard/pos/returns?invoice=${invoiceNumber}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ScrollText className="size-7 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
      </div>

      {/* Search bar */}
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

      {/* Sales table */}
      <div className="rounded-lg border bg-card">
        {isLoading ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {t("loading")}
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {t("noSales")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">
                    {t("invoice")}
                  </th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">
                    {t("dateTime")}
                  </th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">
                    {t("customer")}
                  </th>
                  <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">
                    {t("cashier")}
                  </th>
                  <th className="px-4 py-3 text-center font-semibold">
                    {t("items")}
                  </th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">
                    {t("amount")}
                  </th>
                  <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">
                    {t("discount")}
                  </th>
                  <th className="px-4 py-3 text-center font-semibold">
                    {t("status")}
                  </th>
                  <th className="px-4 py-3 text-center font-semibold">
                    {t("actions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((sale) => (
                  <tr
                    key={sale.id}
                    className="border-b last:border-0 hover:bg-muted/50"
                  >
                    <td className="px-4 py-3 font-mono text-xs font-medium">
                      {sale.invoice_number}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div>{fmtDate(sale.date, locale)}</div>
                      <div className="text-xs text-muted-foreground">
                        {fmtTime(sale.date, locale)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {sale.customer_name || (
                        <span className="text-muted-foreground">
                          {t("walkIn")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {sale.cashier}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums">
                      {sale.item_count}
                    </td>
                    <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums font-medium">
                      {fmtNumber(sale.total_amount, locale)} SAR
                    </td>
                    <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums text-muted-foreground">
                      {sale.discount_amount && parseFloat(sale.discount_amount) > 0
                        ? `${fmtNumber(sale.discount_amount, locale)} SAR`
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          sale.status === "PAID"
                            ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
                        )}
                      >
                        {sale.status === "PAID" ? t("paid") : t("returned")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 px-2"
                          onClick={() => handleReprint(sale.invoice_number)}
                          title={t("reprint")}
                        >
                          <Printer className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 px-2"
                          onClick={() =>
                            handleIssueReturn(sale.invoice_number)
                          }
                          title={t("issueReturn")}
                        >
                          <RotateCcw className="size-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Receipt reprint modal */}
      {receiptData && (
        <InvoiceModal
          invoice={receiptData}
          onClose={() => setReceiptData(null)}
        />
      )}
    </div>
  );
}
