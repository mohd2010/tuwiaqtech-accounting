"use client";

import { useLocale, useTranslations } from "next-intl";
import { Printer, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { fmtNumber, fmtDate } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface QuoteLineItem {
  product_name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface QuotePDFData {
  quote_number: string;
  customer_name: string;
  customer_vat: string | null;
  created_at: string;
  expiry_date: string;
  items: QuoteLineItem[];
  total_amount: string;
  notes: string | null;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function QuotePDFModal({
  quote,
  onClose,
}: {
  quote: QuotePDFData;
  onClose: () => void;
}) {
  const locale = useLocale();
  const t = useTranslations("quotes");
  const fmt = (v: string) => fmtNumber(v, locale);

  const grandTotal = Number(quote.total_amount);
  const vatAmount = (grandTotal * 15) / 115;
  const netAmount = grandTotal - vatAmount;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-2xl p-0 gap-0 print:border-none print:shadow-none"
      >
        <DialogTitle className="sr-only">
          {t("pdfTitle")} {quote.quote_number}
        </DialogTitle>

        {/* ── Printable A4 area ────────────────────────────────────── */}
        <div
          id="quote-pdf"
          dir="rtl"
          className="px-10 py-8 text-sm"
          style={{ fontFamily: "var(--font-almarai), sans-serif" }}
        >
          {/* ── Header ──────────────────────────────────────────── */}
          <div className="text-center">
            <h2 className="text-2xl font-extrabold tracking-wide">
              {t("pdfSeller")}
            </h2>
            <p className="mt-2 text-lg font-bold">{t("pdfTitle")}</p>
          </div>

          <hr className="my-5 border-foreground/30" />

          {/* ── Quote & Customer Info ───────────────────────────── */}
          <div className="grid grid-cols-2 gap-6 text-xs">
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("pdfVatLabel")}</span>
                <span className="font-mono font-medium">399999999999993</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("pdfQuoteNo")}</span>
                <span className="font-medium">{quote.quote_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("pdfDate")}</span>
                <span className="font-medium">{fmtDate(quote.created_at, locale)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("pdfExpiry")}</span>
                <span className="font-medium">{fmtDate(quote.expiry_date, locale)}</span>
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("pdfCustomer")}</span>
                <span className="font-medium">{quote.customer_name}</span>
              </div>
              {quote.customer_vat && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("pdfCustomerVat")}</span>
                  <span className="font-mono font-medium">{quote.customer_vat}</span>
                </div>
              )}
            </div>
          </div>

          <hr className="my-5 border-foreground/30" />

          {/* ── Items Table ─────────────────────────────────────── */}
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b-2 border-foreground/30 text-muted-foreground">
                <th className="pb-2 text-right font-semibold w-8">#</th>
                <th className="pb-2 text-right font-semibold">{t("pdfItem")}</th>
                <th className="pb-2 text-center font-semibold">{t("pdfQty")}</th>
                <th className="pb-2 text-left font-semibold">{t("pdfPrice")}</th>
                <th className="pb-2 text-left font-semibold">{t("pdfTotal")}</th>
              </tr>
            </thead>
            <tbody>
              {quote.items.map((item, idx) => (
                <tr key={idx} className="border-b border-foreground/10">
                  <td className="py-2.5 text-right tabular-nums text-muted-foreground">{idx + 1}</td>
                  <td className="py-2.5 pr-2">{item.product_name}</td>
                  <td className="py-2.5 text-center tabular-nums">{item.quantity}</td>
                  <td className="py-2.5 text-left tabular-nums">{fmt(item.unit_price)}</td>
                  <td className="py-2.5 text-left tabular-nums font-medium">{fmt(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <hr className="my-5 border-foreground/30" />

          {/* ── Totals ──────────────────────────────────────────── */}
          <div className="ltr:ml-auto rtl:mr-auto w-64 space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("pdfSubtotal")}</span>
              <span className="tabular-nums">{fmt(String(netAmount.toFixed(2)))} SAR</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("pdfVatTotal")}</span>
              <span className="tabular-nums">{fmt(String(vatAmount.toFixed(2)))} SAR</span>
            </div>
            <div className="flex justify-between border-t-2 border-foreground/40 pt-2 text-sm font-extrabold">
              <span>{t("pdfGrandTotal")}</span>
              <span className="tabular-nums">{fmt(quote.total_amount)} SAR</span>
            </div>
          </div>

          {/* ── Notes ───────────────────────────────────────────── */}
          {quote.notes && (
            <div className="mt-6 rounded border border-foreground/10 p-3 text-xs text-muted-foreground">
              {quote.notes}
            </div>
          )}

          {/* ── Footer ──────────────────────────────────────────── */}
          <div className="mt-8 text-center text-[10px] text-muted-foreground">
            {t("pdfFooter")}
          </div>
        </div>

        {/* ── Action buttons (hidden when printing) ────────────── */}
        <div className="flex gap-2 border-t px-6 py-4 print:hidden">
          <Button className="flex-1" onClick={() => window.print()}>
            <Printer className="size-4" />
            {t("pdfPrint")}
          </Button>
          <Button variant="outline" onClick={onClose}>
            <X className="size-4" />
            {t("pdfClose")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
