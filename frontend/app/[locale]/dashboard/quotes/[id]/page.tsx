"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import {
  FileCheck,
  Printer,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
  Send,
  ThumbsUp,
  ThumbsDown,
  ArrowRightLeft,
} from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate } from "@/lib/format";
import InvoiceModal, { type InvoiceData } from "@/components/pos/InvoiceModal";
import QuotePDFModal, { type QuotePDFData } from "@/components/quotes/QuotePDFModal";
import { Link } from "@/i18n/navigation";

// ─── Types ───────────────────────────────────────────────────────────────────

interface QuoteItemData {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

interface QuoteData {
  id: string;
  quote_number: string;
  customer_name: string;
  customer_vat: string | null;
  status: string;
  expiry_date: string;
  total_amount: string;
  notes: string | null;
  invoice_number: string | null;
  created_by: string;
  created_at: string;
  items: QuoteItemData[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700 dark:bg-gray-800/40 dark:text-gray-300",
  SENT: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  ACCEPTED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  REJECTED: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  CONVERTED: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
};

// ─── Page ────────────────────────────────────────────────────────────────────

export default function QuoteDetailPage() {
  const t = useTranslations("quotes");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams();
  const quoteId = params.id as string;
  const queryClient = useQueryClient();

  const [showPDF, setShowPDF] = useState(false);
  const [invoiceData, setInvoiceData] = useState<InvoiceData | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Fetch quote detail
  const { data: quote, isLoading } = useQuery<QuoteData>({
    queryKey: ["quote", quoteId],
    queryFn: () => api.get(`/api/v1/quotes/${quoteId}`).then((r) => r.data),
  });

  // Status update mutation
  const statusMutation = useMutation({
    mutationFn: async (newStatus: string) => {
      const res = await api.patch(`/api/v1/quotes/${quoteId}/status`, {
        status: newStatus,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quote", quoteId] });
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      showToast(t("statusUpdated"), "success");
    },
    onError: () => {
      showToast(t("statusFailed"), "error");
    },
  });

  // Convert mutation
  const convertMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/api/v1/quotes/${quoteId}/convert`);
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["quote", quoteId] });
      queryClient.invalidateQueries({ queryKey: ["quotes"] });
      showToast(t("convertSuccess"), "success");
      // Show the invoice receipt
      setInvoiceData(data.invoice_data);
    },
    onError: () => {
      showToast(t("convertFailed"), "error");
    },
  });

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

  if (isLoading || !quote) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        {t("loading")}
      </p>
    );
  }

  const grandTotal = Number(quote.total_amount);
  const vatAmount = (grandTotal * 15) / 115;
  const netAmount = grandTotal - vatAmount;

  const canConvert = quote.status === "ACCEPTED" || quote.status === "SENT";
  const canChangeStatus = quote.status !== "CONVERTED";

  // Build PDF data
  const pdfData: QuotePDFData = {
    quote_number: quote.quote_number,
    customer_name: quote.customer_name,
    customer_vat: quote.customer_vat,
    created_at: quote.created_at,
    expiry_date: quote.expiry_date,
    items: quote.items.map((qi) => ({
      product_name: qi.product_name,
      quantity: qi.quantity,
      unit_price: qi.unit_price,
      line_total: qi.line_total,
    })),
    total_amount: quote.total_amount,
    notes: quote.notes,
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileCheck className="size-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">{quote.quote_number}</h1>
            <p className="text-sm text-muted-foreground">{t("detailTitle")}</p>
          </div>
          <span
            className={cn(
              "ltr:ml-3 rtl:mr-3 inline-block rounded-full px-3 py-1 text-xs font-semibold",
              STATUS_COLORS[quote.status] ?? "",
            )}
          >
            {statusLabel(quote.status)}
          </span>
        </div>
        <Link href="/dashboard/quotes">
          <Button variant="outline" size="sm">
            <ArrowLeft className="size-4 ltr:mr-1 rtl:ml-1" />
            {t("backToList")}
          </Button>
        </Link>
      </div>

      {/* Quote Info */}
      <div className="rounded-lg border bg-card p-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">{t("customer")}:</span>{" "}
            <span className="font-medium">{quote.customer_name}</span>
          </div>
          {quote.customer_vat && (
            <div>
              <span className="text-muted-foreground">{t("vatNumber")}:</span>{" "}
              <span className="font-mono font-medium">{quote.customer_vat}</span>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">{t("createdOn")}:</span>{" "}
            <span className="font-medium">{fmtDate(quote.created_at, locale)}</span>
          </div>
          <div>
            <span className="text-muted-foreground">{t("expiresOn")}:</span>{" "}
            <span className="font-medium">{fmtDate(quote.expiry_date, locale)}</span>
          </div>
          {quote.invoice_number && (
            <div className="col-span-2">
              <span className="text-muted-foreground">Invoice:</span>{" "}
              <span className="font-mono font-medium text-primary">{quote.invoice_number}</span>
            </div>
          )}
        </div>
      </div>

      {/* Items Table */}
      <div className="rounded-lg border bg-card">
        <div className="border-b px-4 py-3">
          <h2 className="text-lg font-semibold">{t("items")}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold w-8">#</th>
                <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("product")}</th>
                <th className="px-4 py-3 text-center font-semibold">{t("qty")}</th>
                <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("unitPrice")}</th>
                <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("lineTotal")}</th>
              </tr>
            </thead>
            <tbody>
              {quote.items.map((item, idx) => (
                <tr key={item.id} className="border-b last:border-0">
                  <td className="px-4 py-3 text-muted-foreground">{idx + 1}</td>
                  <td className="px-4 py-3 font-medium">{item.product_name}</td>
                  <td className="px-4 py-3 text-center tabular-nums">{item.quantity}</td>
                  <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums">
                    {fmtNumber(item.unit_price, locale)} SAR
                  </td>
                  <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums font-medium">
                    {fmtNumber(item.line_total, locale)} SAR
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Totals */}
        <div className="border-t px-4 py-4">
          <div className="ltr:ml-auto rtl:mr-auto w-64 space-y-1.5 text-sm">
            <div className="flex justify-between text-muted-foreground">
              <span>{t("subtotalExclVat")}</span>
              <span className="tabular-nums">{fmtNumber(String(netAmount.toFixed(2)), locale)} SAR</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>{t("vat15")}</span>
              <span className="tabular-nums">{fmtNumber(String(vatAmount.toFixed(2)), locale)} SAR</span>
            </div>
            <div className="flex justify-between border-t pt-2 text-lg font-bold">
              <span>{t("total")}</span>
              <span className="tabular-nums">{fmtNumber(quote.total_amount, locale)} SAR</span>
            </div>
          </div>
        </div>
      </div>

      {/* Notes */}
      {quote.notes && (
        <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{t("notes")}:</span> {quote.notes}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => setShowPDF(true)}>
          <Printer className="size-4 ltr:mr-1 rtl:ml-1" />
          {t("printPdf")}
        </Button>

        {canChangeStatus && quote.status === "DRAFT" && (
          <Button
            variant="outline"
            onClick={() => statusMutation.mutate("SENT")}
            disabled={statusMutation.isPending}
          >
            <Send className="size-4 ltr:mr-1 rtl:ml-1" />
            {t("markSent")}
          </Button>
        )}

        {canChangeStatus && quote.status !== "ACCEPTED" && quote.status !== "CONVERTED" && (
          <Button
            variant="outline"
            className="border-green-500/30 text-green-700 hover:bg-green-50 dark:text-green-400 dark:hover:bg-green-950/20"
            onClick={() => statusMutation.mutate("ACCEPTED")}
            disabled={statusMutation.isPending}
          >
            <ThumbsUp className="size-4 ltr:mr-1 rtl:ml-1" />
            {t("markAccepted")}
          </Button>
        )}

        {canChangeStatus && quote.status !== "REJECTED" && quote.status !== "CONVERTED" && (
          <Button
            variant="outline"
            className="border-red-500/30 text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/20"
            onClick={() => statusMutation.mutate("REJECTED")}
            disabled={statusMutation.isPending}
          >
            <ThumbsDown className="size-4 ltr:mr-1 rtl:ml-1" />
            {t("markRejected")}
          </Button>
        )}

        {canConvert && (
          <Button
            onClick={() => convertMutation.mutate()}
            disabled={convertMutation.isPending}
          >
            <ArrowRightLeft className="size-4 ltr:mr-1 rtl:ml-1" />
            {convertMutation.isPending ? t("converting") : t("convertToInvoice")}
          </Button>
        )}
      </div>

      {/* PDF Modal */}
      {showPDF && (
        <QuotePDFModal quote={pdfData} onClose={() => setShowPDF(false)} />
      )}

      {/* Invoice Modal (after conversion) */}
      {invoiceData && (
        <InvoiceModal
          invoice={invoiceData}
          onClose={() => setInvoiceData(null)}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 ltr:right-6 rtl:left-6 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg",
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white",
          )}
        >
          {toast.type === "success" && <CheckCircle className="size-4" />}
          {toast.type === "error" && <AlertCircle className="size-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
}
