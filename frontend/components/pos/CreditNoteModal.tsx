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

export interface CreditNoteLineItem {
  product_name: string;
  quantity: number;
  condition: string;
  unit_refund_amount: string;
  line_refund_amount: string;
}

export interface CreditNoteData {
  credit_note_number: string;
  original_invoice_number: string;
  timestamp: string;
  reason: string;
  items: CreditNoteLineItem[];
  total_refund: string;
  net_refund: string;
  vat_refund: string;
  qr_code: string;
  journal_entry_id: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function CreditNoteModal({
  creditNote,
  onClose,
}: {
  creditNote: CreditNoteData;
  onClose: () => void;
}) {
  const locale = useLocale();
  const t = useTranslations("CreditNote");
  const fmt = (v: string) => fmtNumber(v, locale);
  const date = fmtDate(creditNote.timestamp, locale);
  const time = fmtTime(creditNote.timestamp, locale);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-md p-0 gap-0 print:border-none print:shadow-none"
      >
        {/* Visually-hidden accessible title */}
        <DialogTitle className="sr-only">
          Credit Note {creditNote.credit_note_number}
        </DialogTitle>

        {/* ── Receipt (printable area) ─────────────────────────────── */}
        <div
          id="credit-note-receipt"
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

          {/* ── Title: Bilingual credit note title ───────────────── */}
          <div className="mt-3 text-center">
            <p className="text-base font-bold">{t("title")}</p>
          </div>

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-4 border-dashed border-foreground/30" />

          {/* ── Details — bilingual labels ────────────────────────── */}
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
              <span className="text-muted-foreground">{t("credit_note_number")}</span>
              <span className="font-medium">{creditNote.credit_note_number}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("original_invoice")}</span>
              <span className="font-medium">{creditNote.original_invoice_number}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("date")}</span>
              <span className="font-medium">{date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("time")}</span>
              <span className="font-medium">{time}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("reason")}</span>
              <span className="font-medium">{creditNote.reason}</span>
            </div>
          </div>

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-4 border-dashed border-foreground/30" />

          {/* ── Item Table ───────────────────────────────────────── */}
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-foreground/20 text-muted-foreground">
                <th className="pb-2 text-right font-semibold">{t("item")}</th>
                <th className="pb-2 text-center font-semibold">{t("qty")}</th>
                <th className="pb-2 text-center font-semibold">{t("condition")}</th>
                <th className="pb-2 text-left font-semibold">{t("price")}</th>
                <th className="pb-2 text-left font-semibold">{t("total")}</th>
              </tr>
            </thead>
            <tbody>
              {creditNote.items.map((item, idx) => (
                <tr key={idx} className="border-b border-dashed border-foreground/10 last:border-0">
                  <td className="py-2 pl-2">{item.product_name}</td>
                  <td className="py-2 text-center tabular-nums">{item.quantity}</td>
                  <td className="py-2 text-center text-[10px]">
                    {item.condition === "RESALABLE" ? t("resalable") : t("damaged")}
                  </td>
                  <td className="py-2 text-left tabular-nums">-{fmt(item.unit_refund_amount)}</td>
                  <td className="py-2 text-left tabular-nums font-medium">-{fmt(item.line_refund_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-4 border-dashed border-foreground/30" />

          {/* ── Totals ───────────────────────────────────────────── */}
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("subtotal")}</span>
              <span className="tabular-nums">-{fmt(creditNote.net_refund)} SAR</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("vat_total")}</span>
              <span className="tabular-nums">-{fmt(creditNote.vat_refund)} SAR</span>
            </div>
            <div className="mt-2 flex justify-between border-t-2 border-foreground/40 pt-2 text-sm font-extrabold">
              <span>{t("grand_total")}</span>
              <span className="tabular-nums">-{fmt(creditNote.total_refund)} SAR</span>
            </div>
          </div>

          {/* ── Divider ──────────────────────────────────────────── */}
          <hr className="my-5 border-dashed border-foreground/30" />

          {/* ── ZATCA QR Code ────────────────────────────────────── */}
          <div className="flex flex-col items-center gap-3 pb-2">
            <QRCode value={creditNote.qr_code} size={128} level="M" />
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
