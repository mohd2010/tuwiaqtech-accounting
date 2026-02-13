"use client";

import { useLocale, useTranslations } from "next-intl";
import QRCode from "react-qr-code";
import { Printer, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { fmtNumber, fmtDate, fmtTime } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface InvoiceLineItem {
  product: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface InvoiceData {
  invoice_number: string;
  timestamp: string;
  items: InvoiceLineItem[];
  total_collected: string;
  net_revenue: string;
  vat_amount: string;
  qr_code: string;
  journal_entry_id: string;
  payments?: { method: string; amount: string }[];
  discount_amount?: string;
  original_total?: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function InvoiceModal({
  invoice,
  onClose,
}: {
  invoice: InvoiceData;
  onClose: () => void;
}) {
  const locale = useLocale();
  const t = useTranslations("Receipt");
  const fmt = (v: string) => fmtNumber(v, locale);
  const date = fmtDate(invoice.timestamp, locale);
  const time = fmtTime(invoice.timestamp, locale);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-md p-0 gap-0 print:border-none print:shadow-none"
      >
        {/* Visually-hidden accessible title */}
        <DialogTitle className="sr-only">
          Invoice {invoice.invoice_number}
        </DialogTitle>

        {/* ── Receipt (printable area) ─────────────────────────────── */}
        <div
          id="invoice-receipt"
          dir="rtl"
          className="px-8 py-6 text-sm"
          style={{ fontFamily: "var(--font-almarai), sans-serif" }}
        >
          {/* ── Header: Company name centered ────────────────────── */}
          <div className="text-center">
            <h2 className="text-xl font-extrabold tracking-wide">
              {t("sellerName")}
            </h2>
          </div>

          {/* ── Title: Bilingual ZATCA title, bold ────────────────── */}
          <div className="mt-3 text-center">
            <p className="text-base font-bold">{t("title")}</p>
          </div>

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-4 border-dashed border-foreground/30" />

          {/* ── Seller & Invoice Details — bilingual labels ────────── */}
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("seller")}</span>
              <span className="font-medium">{t("sellerName")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("vat_number")}</span>
              <span className="font-mono font-medium">399999999999993</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("invoice_number")}</span>
              <span className="font-medium">{invoice.invoice_number}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("date")}</span>
              <span className="font-medium">{date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("time")}</span>
              <span className="font-medium">{time}</span>
            </div>
          </div>

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-4 border-dashed border-foreground/30" />

          {/* ── Item Table — bilingual headers ─────────────────────── */}
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-foreground/20 text-muted-foreground">
                <th className="pb-2 text-right font-semibold">
                  {t("item")}
                </th>
                <th className="pb-2 text-center font-semibold">
                  {t("qty")}
                </th>
                <th className="pb-2 text-left font-semibold">
                  {t("price")}
                </th>
                <th className="pb-2 text-left font-semibold">
                  {t("total")}
                </th>
              </tr>
            </thead>
            <tbody>
              {invoice.items.map((item, idx) => (
                <tr key={`${item.product}-${idx}`} className="border-b border-dashed border-foreground/10 last:border-0">
                  <td className="py-2 pl-2">{item.product}</td>
                  <td className="py-2 text-center tabular-nums">{item.quantity}</td>
                  <td className="py-2 text-left tabular-nums">{fmt(item.unit_price)}</td>
                  <td className="py-2 text-left tabular-nums font-medium">{fmt(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* ── Discount (if any) ─────────────────────────────────── */}
          {invoice.discount_amount && parseFloat(invoice.discount_amount) > 0 && invoice.original_total && (
            <>
              <hr className="my-4 border-dashed border-foreground/30" />
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("itemsTotal")}</span>
                  <span className="tabular-nums">{fmt(invoice.original_total)} SAR</span>
                </div>
                <div className="flex justify-between text-green-600 font-medium">
                  <span>{t("discount")}</span>
                  <span className="tabular-nums">-{fmt(invoice.discount_amount)} SAR</span>
                </div>
              </div>
            </>
          )}

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-4 border-dashed border-foreground/30" />

          {/* ── Totals — bilingual labels ──────────────────────────── */}
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("subtotal")}</span>
              <span className="tabular-nums">{fmt(invoice.net_revenue)} SAR</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("vat_total")}</span>
              <span className="tabular-nums">{fmt(invoice.vat_amount)} SAR</span>
            </div>
            <div className="mt-2 flex justify-between border-t-2 border-foreground/40 pt-2 text-sm font-extrabold">
              <span>{t("grand_total")}</span>
              <span className="tabular-nums">{fmt(invoice.total_collected)} SAR</span>
            </div>
          </div>

          {/* ── Payment Method Breakdown ────────────────────────── */}
          {invoice.payments && invoice.payments.length > 0 && (
            <>
              <hr className="my-3 border-dashed border-foreground/30" />
              <div className="space-y-1 text-xs">
                <p className="font-semibold text-muted-foreground">{t("paymentMethod")}</p>
                {invoice.payments.map((p, idx) => (
                  <div key={`${p.method}-${idx}`} className="flex justify-between">
                    <span>{t(`method_${p.method}`)}</span>
                    <span className="tabular-nums">{fmt(p.amount)} SAR</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-5 border-dashed border-foreground/30" />

          {/* ── ZATCA QR Code — centered with whitespace ──────────── */}
          <div className="flex flex-col items-center gap-3 pb-2">
            <QRCode value={invoice.qr_code} size={128} level="M" />
            <p className="text-center text-[10px] leading-tight text-muted-foreground">
              {t("scanZatca")}
            </p>
          </div>
        </div>

        {/* ── Action buttons (hidden when printing) ───────────────── */}
        <div className="flex gap-2 border-t px-6 py-4 print:hidden">
          <Button className="flex-1" onClick={() => window.print()}>
            <Printer className="size-4" />
            {t("print")}
          </Button>
          <Button variant="outline" onClick={onClose}>
            <X className="size-4" />
            {t("close")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
