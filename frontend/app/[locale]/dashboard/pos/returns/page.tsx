"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import {
  Search,
  RotateCcw,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import CreditNoteModal, {
  type CreditNoteData,
} from "@/components/pos/CreditNoteModal";

// ─── Types ───────────────────────────────────────────────────────────────────

interface LookupItem {
  product_id: string;
  product_name: string;
  sku: string;
  quantity_sold: number;
  quantity_returned: number;
  returnable_quantity: number;
  unit_price: string;
  cost_price: string;
}

interface InvoiceLookup {
  invoice_number: string;
  journal_entry_id: string;
  timestamp: string;
  customer_id: string | null;
  items: LookupItem[];
  total_amount: string;
  vat_amount: string;
  net_amount: string;
}

interface ReturnLineItem {
  product_id: string;
  product_name: string;
  quantity: number;
  max_quantity: number;
  condition: "RESALABLE" | "DAMAGED";
  unit_price: string;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ReturnsPage() {
  const t = useTranslations("returns");
  const locale = useLocale();
  const searchParams = useSearchParams();

  // Wizard step: 0=find, 1=select, 2=confirm, 3=receipt
  const [step, setStep] = useState(0);

  // Step 0: Find Invoice
  const [invoiceInput, setInvoiceInput] = useState("");
  const [lookupData, setLookupData] = useState<InvoiceLookup | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);

  // Step 1: Select Items
  const [returnItems, setReturnItems] = useState<ReturnLineItem[]>([]);
  const [reason, setReason] = useState("");

  // Step 2-3: Confirm & Receipt
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState("");
  const [creditNote, setCreditNote] = useState<CreditNoteData | null>(null);

  // Toast
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const showToast = useCallback(
    (message: string, type: "success" | "error") => {
      setToast({ message, type });
      setTimeout(() => setToast(null), 3000);
    },
    [],
  );

  // Auto-fill invoice from URL query param (e.g. ?invoice=INV-2026-0001)
  const [autoLoaded, setAutoLoaded] = useState(false);
  useEffect(() => {
    const inv = searchParams.get("invoice");
    if (inv && !autoLoaded && step === 0) {
      setInvoiceInput(inv);
      setAutoLoaded(true);
    }
  }, [searchParams, autoLoaded, step]);

  // ── Step 0: Look up invoice ────────────────────────────────────────────

  const handleLookup = async () => {
    const num = invoiceInput.trim();
    if (!num) return;

    setLookupError("");
    setLookupLoading(true);
    try {
      const res = await api.get(`/api/v1/returns/invoice/${encodeURIComponent(num)}`);
      const data = res.data as InvoiceLookup;

      // Filter to items that still have returnable quantity
      const returnable = data.items.filter((i) => i.returnable_quantity > 0);
      if (returnable.length === 0) {
        setLookupError(t("allReturned"));
        setLookupLoading(false);
        return;
      }

      setLookupData(data);
      // Initialize return items with 0 quantity
      setReturnItems(
        returnable.map((i) => ({
          product_id: i.product_id,
          product_name: i.product_name,
          quantity: 0,
          max_quantity: i.returnable_quantity,
          condition: "RESALABLE",
          unit_price: i.unit_price,
        })),
      );
      setStep(1);
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail
          : undefined;
      setLookupError(detail ?? t("invoiceNotFound"));
    } finally {
      setLookupLoading(false);
    }
  };

  // ── Step 1: Update return line items ───────────────────────────────────

  const updateItemQty = (idx: number, qty: number) => {
    setReturnItems((prev) =>
      prev.map((item, i) =>
        i === idx
          ? { ...item, quantity: Math.max(0, Math.min(qty, item.max_quantity)) }
          : item,
      ),
    );
  };

  const updateItemCondition = (idx: number, condition: "RESALABLE" | "DAMAGED") => {
    setReturnItems((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, condition } : item)),
    );
  };

  const selectedItems = returnItems.filter((i) => i.quantity > 0);
  const canProceed = selectedItems.length > 0 && reason.trim().length > 0;

  // ── Step 2: Process return ─────────────────────────────────────────────

  const handleProcessReturn = async () => {
    if (!lookupData) return;

    setProcessing(true);
    setProcessError("");
    try {
      const res = await api.post("/api/v1/returns/process", {
        invoice_number: lookupData.invoice_number,
        items: selectedItems.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
          condition: i.condition,
        })),
        reason: reason.trim(),
      });
      setCreditNote(res.data as CreditNoteData);
      setStep(3);
      showToast(t("returnSuccess"), "success");
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail
          : undefined;
      setProcessError(detail ?? t("returnFailed"));
      showToast(t("returnFailed"), "error");
    } finally {
      setProcessing(false);
    }
  };

  // ── Reset wizard ───────────────────────────────────────────────────────

  const resetWizard = () => {
    setStep(0);
    setInvoiceInput("");
    setLookupData(null);
    setLookupError("");
    setReturnItems([]);
    setReason("");
    setProcessError("");
    setCreditNote(null);
  };

  // ── Refund summary calculations ────────────────────────────────────────

  const grossRefund = selectedItems.reduce(
    (sum, i) => sum + Number(i.unit_price) * i.quantity,
    0,
  );
  const vatRefund = (grossRefund * 15) / 115;
  const netRefund = grossRefund - vatRefund;

  // ── Step labels for progress bar ───────────────────────────────────────

  const steps = [t("stepFind"), t("stepSelect"), t("stepConfirm"), t("stepReceipt")];

  return (
    <div className="mx-auto max-w-4xl">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="mb-6 flex items-center gap-3">
        <RotateCcw className="size-7 text-primary" />
        <h1 className="text-3xl font-bold">{t("title")}</h1>
      </div>

      {/* ── Step progress ───────────────────────────────────────────── */}
      <div className="mb-8 flex items-center gap-2">
        {steps.map((label, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div
              className={cn(
                "flex size-8 items-center justify-center rounded-full text-sm font-bold transition-colors",
                idx < step
                  ? "bg-primary text-primary-foreground"
                  : idx === step
                    ? "bg-primary text-primary-foreground ring-2 ring-primary/30"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {idx < step ? <CheckCircle className="size-4" /> : idx + 1}
            </div>
            <span
              className={cn(
                "text-sm font-medium",
                idx <= step ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {label}
            </span>
            {idx < steps.length - 1 && (
              <div
                className={cn(
                  "h-px w-8",
                  idx < step ? "bg-primary" : "bg-border",
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* ─────────────────────────────────────────────────────────────── */}
      {/* STEP 0: Find Invoice                                           */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">{t("findInvoice")}</h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={invoiceInput}
              onChange={(e) => setInvoiceInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleLookup();
                }
              }}
              placeholder={t("invoicePlaceholder")}
              className="h-10 flex-1 rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <Button onClick={handleLookup} disabled={lookupLoading || !invoiceInput.trim()}>
              <Search className="size-4 ltr:mr-1 rtl:ml-1" />
              {lookupLoading ? t("searching") : t("search")}
            </Button>
          </div>
          {lookupError && (
            <div className="mt-3 flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="size-4" />
              {lookupError}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────── */}
      {/* STEP 1: Select Items                                           */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 1 && lookupData && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{t("selectItems")}</h2>
              <span className="text-sm text-muted-foreground">
                {lookupData.invoice_number}
              </span>
            </div>

            {/* Items table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="pb-2 text-left font-semibold">{t("product")}</th>
                    <th className="pb-2 text-center font-semibold">{t("sold")}</th>
                    <th className="pb-2 text-center font-semibold">{t("returnable")}</th>
                    <th className="pb-2 text-center font-semibold">{t("returnQty")}</th>
                    <th className="pb-2 text-center font-semibold">{t("conditionLabel")}</th>
                    <th className="pb-2 text-right font-semibold">{t("unitPrice")}</th>
                  </tr>
                </thead>
                <tbody>
                  {returnItems.map((item, idx) => (
                    <tr key={item.product_id} className="border-b last:border-0">
                      <td className="py-3 font-medium">{item.product_name}</td>
                      <td className="py-3 text-center tabular-nums">
                        {lookupData.items.find((i) => i.product_id === item.product_id)
                          ?.quantity_sold ?? 0}
                      </td>
                      <td className="py-3 text-center tabular-nums">
                        {item.max_quantity}
                      </td>
                      <td className="py-3">
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            size="icon-xs"
                            variant="outline"
                            onClick={() => updateItemQty(idx, item.quantity - 1)}
                            disabled={item.quantity === 0}
                          >
                            <span className="text-xs font-bold">-</span>
                          </Button>
                          <span className="w-8 text-center tabular-nums font-medium">
                            {item.quantity}
                          </span>
                          <Button
                            size="icon-xs"
                            variant="outline"
                            onClick={() => updateItemQty(idx, item.quantity + 1)}
                            disabled={item.quantity >= item.max_quantity}
                          >
                            <span className="text-xs font-bold">+</span>
                          </Button>
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex justify-center gap-1">
                          <button
                            onClick={() => updateItemCondition(idx, "RESALABLE")}
                            className={cn(
                              "rounded px-2 py-1 text-xs font-medium transition-colors",
                              item.condition === "RESALABLE"
                                ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                                : "bg-muted text-muted-foreground hover:bg-muted/80",
                            )}
                          >
                            {t("resalable")}
                          </button>
                          <button
                            onClick={() => updateItemCondition(idx, "DAMAGED")}
                            className={cn(
                              "rounded px-2 py-1 text-xs font-medium transition-colors",
                              item.condition === "DAMAGED"
                                ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                                : "bg-muted text-muted-foreground hover:bg-muted/80",
                            )}
                          >
                            {t("damaged")}
                          </button>
                        </div>
                      </td>
                      <td className="py-3 text-right tabular-nums">
                        {Number(item.unit_price).toFixed(2)} SAR
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Reason */}
            <div className="mt-4">
              <label className="mb-1 block text-sm font-medium">
                {t("reasonLabel")}
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t("reasonPlaceholder")}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {/* Navigation */}
          <div className="flex justify-between">
            <Button variant="outline" onClick={resetWizard}>
              <ArrowLeft className="size-4 ltr:mr-1 rtl:ml-1" />
              {t("back")}
            </Button>
            <Button onClick={() => setStep(2)} disabled={!canProceed}>
              {t("next")}
              <ArrowRight className="size-4 ltr:ml-1 rtl:mr-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────── */}
      {/* STEP 2: Confirm                                                */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 2 && lookupData && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">{t("confirmReturn")}</h2>

            <div className="mb-3 text-sm text-muted-foreground">
              {t("originalInvoice")}: <span className="font-medium text-foreground">{lookupData.invoice_number}</span>
            </div>

            {/* Summary table */}
            <table className="mb-4 w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 text-left font-semibold">{t("product")}</th>
                  <th className="pb-2 text-center font-semibold">{t("qty")}</th>
                  <th className="pb-2 text-center font-semibold">{t("conditionLabel")}</th>
                  <th className="pb-2 text-right font-semibold">{t("refund")}</th>
                </tr>
              </thead>
              <tbody>
                {selectedItems.map((item) => (
                  <tr key={item.product_id} className="border-b last:border-0">
                    <td className="py-2 font-medium">{item.product_name}</td>
                    <td className="py-2 text-center tabular-nums">{item.quantity}</td>
                    <td className="py-2 text-center">
                      <span
                        className={cn(
                          "rounded px-2 py-0.5 text-xs font-medium",
                          item.condition === "RESALABLE"
                            ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                            : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
                        )}
                      >
                        {item.condition === "RESALABLE" ? t("resalable") : t("damaged")}
                      </span>
                    </td>
                    <td className="py-2 text-right tabular-nums font-medium">
                      -{(Number(item.unit_price) * item.quantity).toFixed(2)} SAR
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Totals */}
            <div className="space-y-1.5 border-t pt-3 text-sm">
              <div className="flex justify-between text-muted-foreground">
                <span>{t("netRefund")}</span>
                <span className="tabular-nums">-{netRefund.toFixed(2)} SAR</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>{t("vatRefund")}</span>
                <span className="tabular-nums">-{vatRefund.toFixed(2)} SAR</span>
              </div>
              <div className="flex justify-between border-t pt-2 text-lg font-bold">
                <span>{t("totalRefund")}</span>
                <span className="tabular-nums">-{grossRefund.toFixed(2)} SAR</span>
              </div>
            </div>

            {/* Reason display */}
            <div className="mt-4 rounded-md bg-muted/50 p-3 text-sm">
              <span className="font-medium">{t("reasonLabel")}:</span> {reason}
            </div>

            {processError && (
              <div className="mt-3 flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="size-4" />
                {processError}
              </div>
            )}
          </div>

          {/* Navigation */}
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(1)}>
              <ArrowLeft className="size-4 ltr:mr-1 rtl:ml-1" />
              {t("back")}
            </Button>
            <Button
              onClick={handleProcessReturn}
              disabled={processing}
              variant="destructive"
            >
              <RotateCcw className="size-4 ltr:mr-1 rtl:ml-1" />
              {processing ? t("processing") : t("confirmReturnBtn")}
            </Button>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────── */}
      {/* STEP 3: Receipt (Credit Note Modal)                            */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 3 && creditNote && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-card p-6 text-center">
            <CheckCircle className="mx-auto mb-3 size-12 text-green-500" />
            <h2 className="text-lg font-semibold">{t("returnComplete")}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("creditNoteIssued")}: {creditNote.credit_note_number}
            </p>
          </div>
          <div className="flex justify-center">
            <Button onClick={resetWizard}>
              <RotateCcw className="size-4 ltr:mr-1 rtl:ml-1" />
              {t("newReturn")}
            </Button>
          </div>

          {/* Credit Note Modal */}
          <CreditNoteModal
            creditNote={creditNote}
            onClose={resetWizard}
          />
        </div>
      )}

      {/* ── Toast ─────────────────────────────────────────────────────── */}
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
          {toast.message}
        </div>
      )}
    </div>
  );
}
