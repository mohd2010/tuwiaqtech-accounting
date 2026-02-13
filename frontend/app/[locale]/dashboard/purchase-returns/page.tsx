"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  RotateCcw,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Search,
} from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface POOption {
  id: string;
  supplier_id: string;
  status: string;
  total_amount: string;
  created_at: string;
}

interface LookupItem {
  product_id: string;
  product_name: string;
  sku: string;
  quantity_ordered: number;
  quantity_returned: number;
  returnable_quantity: number;
  unit_cost: string;
}

interface POLookup {
  po_id: string;
  supplier_name: string;
  received_at: string;
  items: LookupItem[];
  total_amount: string;
}

interface ReturnLineItem {
  product_id: string;
  product_name: string;
  quantity: number;
  max_quantity: number;
  condition: "RESALABLE" | "DAMAGED";
  unit_cost: string;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PurchaseReturnsPage() {
  const t = useTranslations("purchaseReturns");

  // Wizard step: 0=find PO, 1=select items, 2=confirm + result
  const [step, setStep] = useState(0);

  // Step 0: Find PO
  const [poOptions, setPOOptions] = useState<POOption[]>([]);
  const [selectedPOId, setSelectedPOId] = useState("");
  const [lookupData, setLookupData] = useState<POLookup | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [posLoading, setPosLoading] = useState(true);

  // Step 1: Select Items
  const [returnItems, setReturnItems] = useState<ReturnLineItem[]>([]);
  const [reason, setReason] = useState("");

  // Step 2: Confirm & Result
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState("");
  const [returnResult, setReturnResult] = useState<Record<string, unknown> | null>(null);

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

  // Load received POs on mount
  useEffect(() => {
    const fetchPOs = async () => {
      try {
        const res = await api.get("/api/v1/purchase-orders/");
        const all = res.data as POOption[];
        setPOOptions(all.filter((po) => po.status === "RECEIVED"));
      } catch {
        // ignore
      } finally {
        setPosLoading(false);
      }
    };
    fetchPOs();
  }, []);

  // ── Step 0: Look up PO ──────────────────────────────────────────────────

  const handleLookup = async () => {
    if (!selectedPOId) return;

    setLookupError("");
    setLookupLoading(true);
    try {
      const res = await api.get(`/api/v1/purchase-returns/po/${selectedPOId}`);
      const data = res.data as POLookup;

      const returnable = data.items.filter((i) => i.returnable_quantity > 0);
      if (returnable.length === 0) {
        setLookupError(t("noReceivedPOs"));
        setLookupLoading(false);
        return;
      }

      setLookupData(data);
      setReturnItems(
        returnable.map((i) => ({
          product_id: i.product_id,
          product_name: i.product_name,
          quantity: 0,
          max_quantity: i.returnable_quantity,
          condition: "RESALABLE",
          unit_cost: i.unit_cost,
        })),
      );
      setStep(1);
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail
          : undefined;
      setLookupError(detail ?? t("poNotFound"));
    } finally {
      setLookupLoading(false);
    }
  };

  // ── Step 1: Update return line items ─────────────────────────────────────

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

  // ── Step 2: Process return ───────────────────────────────────────────────

  const handleProcessReturn = async () => {
    if (!lookupData) return;

    setProcessing(true);
    setProcessError("");
    try {
      const res = await api.post("/api/v1/purchase-returns/process", {
        po_id: lookupData.po_id,
        items: selectedItems.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
          condition: i.condition,
        })),
        reason: reason.trim(),
      });
      setReturnResult(res.data as Record<string, unknown>);
      setStep(2);
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

  // ── Reset wizard ─────────────────────────────────────────────────────────

  const resetWizard = () => {
    setStep(0);
    setSelectedPOId("");
    setLookupData(null);
    setLookupError("");
    setReturnItems([]);
    setReason("");
    setProcessError("");
    setReturnResult(null);
  };

  // ── Summary calculations ─────────────────────────────────────────────────

  const totalReturn = selectedItems.reduce(
    (sum, i) => sum + Number(i.unit_cost) * i.quantity,
    0,
  );

  // ── Step labels for progress bar ─────────────────────────────────────────

  const steps = [t("stepFind"), t("stepSelect"), t("stepConfirm")];

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
      {/* STEP 0: Find PO                                                */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">{t("findPO")}</h2>
          <p className="mb-3 text-sm text-muted-foreground">{t("selectPO")}</p>

          {posLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : poOptions.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noReceivedPOs")}</p>
          ) : (
            <div className="flex gap-2">
              <select
                value={selectedPOId}
                onChange={(e) => setSelectedPOId(e.target.value)}
                className="h-10 flex-1 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">{t("selectPO")}</option>
                {poOptions.map((po) => (
                  <option key={po.id} value={po.id}>
                    PO {po.id.slice(0, 8).toUpperCase()} — {Number(po.total_amount).toFixed(2)} SAR — {new Date(po.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
              <Button onClick={handleLookup} disabled={lookupLoading || !selectedPOId}>
                <Search className="size-4 ltr:mr-1 rtl:ml-1" />
                {lookupLoading ? "..." : t("lookup")}
              </Button>
            </div>
          )}
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
                {t("supplier")}: {lookupData.supplier_name}
              </span>
            </div>

            {/* Items table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="pb-2 text-left font-semibold">{t("product")}</th>
                    <th className="pb-2 text-center font-semibold">{t("ordered")}</th>
                    <th className="pb-2 text-center font-semibold">{t("returned")}</th>
                    <th className="pb-2 text-center font-semibold">{t("returnable")}</th>
                    <th className="pb-2 text-center font-semibold">{t("returnQty")}</th>
                    <th className="pb-2 text-center font-semibold">{t("conditionLabel")}</th>
                    <th className="pb-2 text-right font-semibold">{t("unitCost")}</th>
                  </tr>
                </thead>
                <tbody>
                  {returnItems.map((item, idx) => {
                    const lookupItem = lookupData.items.find(
                      (i) => i.product_id === item.product_id,
                    );
                    return (
                      <tr key={item.product_id} className="border-b last:border-0">
                        <td className="py-3 font-medium">{item.product_name}</td>
                        <td className="py-3 text-center tabular-nums">
                          {lookupItem?.quantity_ordered ?? 0}
                        </td>
                        <td className="py-3 text-center tabular-nums">
                          {lookupItem?.quantity_returned ?? 0}
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
                          {Number(item.unit_cost).toFixed(2)} SAR
                        </td>
                      </tr>
                    );
                  })}
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

            {/* Total */}
            <div className="mt-4 flex justify-end">
              <div className="text-lg font-bold">
                {t("totalReturn")}: {totalReturn.toFixed(2)} SAR
              </div>
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
      {/* STEP 2: Confirm & Result                                       */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 2 && !returnResult && lookupData && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">{t("confirmReturn")}</h2>

            <div className="mb-3 text-sm text-muted-foreground">
              {t("supplier")}: <span className="font-medium text-foreground">{lookupData.supplier_name}</span>
            </div>

            {/* Summary table */}
            <table className="mb-4 w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 text-left font-semibold">{t("product")}</th>
                  <th className="pb-2 text-center font-semibold">{t("returnQty")}</th>
                  <th className="pb-2 text-center font-semibold">{t("conditionLabel")}</th>
                  <th className="pb-2 text-right font-semibold">{t("unitCost")}</th>
                  <th className="pb-2 text-right font-semibold">{t("totalReturn")}</th>
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
                    <td className="py-2 text-right tabular-nums">
                      {Number(item.unit_cost).toFixed(2)}
                    </td>
                    <td className="py-2 text-right tabular-nums font-medium">
                      {(Number(item.unit_cost) * item.quantity).toFixed(2)} SAR
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Total */}
            <div className="flex justify-between border-t pt-3 text-lg font-bold">
              <span>{t("totalReturn")}</span>
              <span className="tabular-nums">{totalReturn.toFixed(2)} SAR</span>
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
              {processing ? t("processing") : t("processReturn")}
            </Button>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────── */}
      {/* STEP 2: Result (after success)                                 */}
      {/* ─────────────────────────────────────────────────────────────── */}
      {step === 2 && returnResult && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-card p-6 text-center">
            <CheckCircle className="mx-auto mb-3 size-12 text-green-500" />
            <h2 className="text-lg font-semibold">{t("returnComplete")}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("returnNumber")}: {returnResult.return_number as string}
            </p>
          </div>
          <div className="flex justify-center">
            <Button onClick={resetWizard}>
              <RotateCcw className="size-4 ltr:mr-1 rtl:ml-1" />
              {t("newReturn")}
            </Button>
          </div>
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
