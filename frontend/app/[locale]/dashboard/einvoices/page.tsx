"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  FileCheck,
  Send,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  AlertCircle,
  Download,
  FileText,
} from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtNumber, fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

// ─── Types ──────────────────────────────────────────────────────────────────

interface EInvoiceRow {
  id: string;
  invoice_uuid: string;
  invoice_number: string;
  icv: number;
  type_code: string;
  sub_type: string;
  total_excluding_vat: string;
  total_vat: string;
  total_including_vat: string;
  buyer_name: string | null;
  buyer_vat_number: string | null;
  submission_status: string;
  zatca_clearance_status: string | null;
  zatca_reporting_status: string | null;
  zatca_warnings: { messages: { message: string }[] } | null;
  zatca_errors: { messages: { message: string }[] } | null;
  submitted_at: string | null;
  issue_date: string;
  created_at: string;
}

interface EInvoiceListResponse {
  items: EInvoiceRow[];
  total: number;
}

interface EInvoiceSummary {
  total: number;
  pending: number;
  cleared: number;
  reported: number;
  rejected: number;
  warning: number;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  SUBMITTED: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  CLEARED: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  REPORTED: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  REJECTED: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  WARNING: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
};

const TYPE_CODE_KEY: Record<string, string> = {
  "388": "taxInvoice",
  "381": "creditNote",
  "383": "debitNote",
};

const SUB_TYPE_KEY: Record<string, string> = {
  "0100000": "b2b",
  "0200000": "b2c",
};

// ─── Page ───────────────────────────────────────────────────────────────────

export default function EInvoicesPage() {
  const t = useTranslations("einvoices");
  const tc = useTranslations("common");
  const locale = useLocale();
  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [selectedInvoice, setSelectedInvoice] = useState<EInvoiceRow | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Queries ───────────────────────────────────────────────────────────────

  const { data: summary } = useQuery<EInvoiceSummary>({
    queryKey: ["einvoices", "summary"],
    queryFn: () => api.get("/api/v1/einvoices/summary").then((r) => r.data),
  });

  const { data, isLoading } = useQuery<EInvoiceListResponse>({
    queryKey: ["einvoices", statusFilter],
    queryFn: () =>
      api
        .get("/api/v1/einvoices", { params: statusFilter ? { status: statusFilter } : {} })
        .then((r) => r.data),
  });

  // ── Detail fetch (when dialog opens) ──────────────────────────────────────

  const { data: detail } = useQuery<EInvoiceRow>({
    queryKey: ["einvoices", "detail", selectedInvoice?.invoice_number],
    queryFn: () =>
      api
        .get(`/api/v1/einvoices/${selectedInvoice!.invoice_number}`)
        .then((r) => r.data),
    enabled: !!selectedInvoice,
  });

  // ── Submit mutation ───────────────────────────────────────────────────────

  const submitMutation = useMutation({
    mutationFn: (invoiceNumber: string) =>
      api.post(`/api/v1/einvoices/${invoiceNumber}/submit`).then((r) => r.data as EInvoiceRow),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["einvoices"] });
      showToast(t("submitSuccess"), "success");
      // If the detail dialog is open for this invoice, refresh it
      if (selectedInvoice?.invoice_number === updated.invoice_number) {
        setSelectedInvoice(updated);
      }
    },
    onError: () => {
      showToast(t("submitFailed"), "error");
    },
  });

  // ── XML Download ──────────────────────────────────────────────────────────

  const handleDownloadXml = async (invoiceNumber: string) => {
    try {
      const res = await api.get(`/api/v1/einvoices/${invoiceNumber}/xml`);
      const xmlB64: string = res.data.xml_content;
      const raw = atob(xmlB64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${invoiceNumber}.xml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      showToast(t("submitFailed"), "error");
    }
  };

  // ── Derived values ────────────────────────────────────────────────────────

  const inv = detail ?? selectedInvoice;
  const errors = inv?.zatca_errors?.messages ?? [];
  const warnings = inv?.zatca_warnings?.messages ?? [];

  // ── KPI cards config ──────────────────────────────────────────────────────

  const kpis = [
    {
      label: t("summaryTotal"),
      value: summary?.total ?? 0,
      icon: FileText,
      color: "text-blue-600 dark:text-blue-400",
      bg: "bg-blue-50 dark:bg-blue-950/30",
    },
    {
      label: t("summaryPending"),
      value: summary?.pending ?? 0,
      icon: Clock,
      color: "text-yellow-600 dark:text-yellow-400",
      bg: "bg-yellow-50 dark:bg-yellow-950/30",
    },
    {
      label: t("summaryAccepted"),
      value: (summary?.cleared ?? 0) + (summary?.reported ?? 0),
      icon: CheckCircle,
      color: "text-green-600 dark:text-green-400",
      bg: "bg-green-50 dark:bg-green-950/30",
    },
    {
      label: t("summaryRejected"),
      value: summary?.rejected ?? 0,
      icon: XCircle,
      color: "text-red-600 dark:text-red-400",
      bg: "bg-red-50 dark:bg-red-950/30",
    },
    {
      label: t("summaryWarning"),
      value: summary?.warning ?? 0,
      icon: AlertTriangle,
      color: "text-orange-600 dark:text-orange-400",
      bg: "bg-orange-50 dark:bg-orange-950/30",
    },
  ];

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileCheck className="size-6" />
          <h1 className="text-2xl font-bold">{t("title")}</h1>
        </div>

        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{t("filterAll")}</option>
          <option value="PENDING">{t("statusPending")}</option>
          <option value="CLEARED">{t("statusCleared")}</option>
          <option value="REPORTED">{t("statusReported")}</option>
          <option value="REJECTED">{t("statusRejected")}</option>
          <option value="WARNING">{t("statusWarning")}</option>
        </select>
      </div>

      {/* ── KPI Cards ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {kpi.label}
              </CardTitle>
              <div className={cn("rounded-md p-2", kpi.bg)}>
                <kpi.icon className={cn("size-4", kpi.color)} />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{kpi.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Table ─────────────────────────────────────────────────────────── */}
      {isLoading ? (
        <p className="text-muted-foreground">{tc("loading")}</p>
      ) : !data?.items.length ? (
        <p className="text-muted-foreground">{t("noInvoices")}</p>
      ) : (
        <div className="overflow-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-start font-medium">{t("invoiceNumber")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("uuid")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("icv")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("type")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("subType")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("buyer")}</th>
                <th className="px-4 py-3 text-end font-medium">{t("amount")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("status")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("date")}</th>
                <th className="px-4 py-3 text-start font-medium">{t("submittedAt")}</th>
                <th className="px-4 py-3 text-start font-medium">{tc("actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.items.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer hover:bg-muted/30"
                  onClick={() => setSelectedInvoice(row)}
                >
                  <td className="px-4 py-3 font-mono text-xs">{row.invoice_number}</td>
                  <td className="px-4 py-3 font-mono text-xs" title={row.invoice_uuid}>
                    {row.invoice_uuid.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3">{row.icv}</td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-muted px-2 py-0.5 text-xs">
                      {TYPE_CODE_KEY[row.type_code]
                        ? t(TYPE_CODE_KEY[row.type_code])
                        : row.type_code}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "rounded px-2 py-0.5 text-xs font-medium",
                        row.sub_type === "0100000"
                          ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300"
                          : "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300",
                      )}
                    >
                      {SUB_TYPE_KEY[row.sub_type]
                        ? t(SUB_TYPE_KEY[row.sub_type])
                        : row.sub_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">{row.buyer_name ?? "—"}</td>
                  <td className="px-4 py-3 text-end font-mono">
                    {fmtNumber(row.total_including_vat, locale)} {tc("sar")}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold",
                        STATUS_COLORS[row.submission_status] ?? "bg-gray-100 text-gray-800",
                      )}
                    >
                      {t(`status${row.submission_status.charAt(0)}${row.submission_status.slice(1).toLowerCase()}`)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs">{fmtDate(row.issue_date, locale)}</td>
                  <td className="px-4 py-3 text-xs">
                    {row.submitted_at ? fmtDate(row.submitted_at, locale) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {(row.submission_status === "PENDING" ||
                      row.submission_status === "REJECTED") && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          submitMutation.mutate(row.invoice_number);
                        }}
                        disabled={submitMutation.isPending}
                      >
                        <Send className="mr-1 size-3" />
                        {submitMutation.isPending ? t("submitting") : t("submit")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <p className="text-sm text-muted-foreground">
          {t("totalCount", { count: data.total })}
        </p>
      )}

      {/* ── Detail Dialog ─────────────────────────────────────────────────── */}
      <Dialog open={!!selectedInvoice} onOpenChange={(open) => !open && setSelectedInvoice(null)}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("invoiceDetail")}</DialogTitle>
          </DialogHeader>

          {inv && (
            <div className="space-y-4">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">{t("invoiceNumber")}</span>
                  <p className="font-mono font-medium">{inv.invoice_number}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">{t("uuid")}</span>
                  <p className="font-mono text-xs break-all">{inv.invoice_uuid}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">{t("icv")}</span>
                  <p className="font-medium">{inv.icv}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">{t("type")}</span>
                  <p>
                    {TYPE_CODE_KEY[inv.type_code]
                      ? t(TYPE_CODE_KEY[inv.type_code])
                      : inv.type_code}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">{t("subType")}</span>
                  <p>
                    <span
                      className={cn(
                        "rounded px-2 py-0.5 text-xs font-medium",
                        inv.sub_type === "0100000"
                          ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300"
                          : "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300",
                      )}
                    >
                      {SUB_TYPE_KEY[inv.sub_type] ? t(SUB_TYPE_KEY[inv.sub_type]) : inv.sub_type}
                    </span>
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">{t("date")}</span>
                  <p>{fmtDate(inv.issue_date, locale)}</p>
                </div>
                {inv.submitted_at && (
                  <div>
                    <span className="text-muted-foreground">{t("submittedAt")}</span>
                    <p>{fmtDate(inv.submitted_at, locale)}</p>
                  </div>
                )}
                <div>
                  <span className="text-muted-foreground">{t("status")}</span>
                  <p>
                    <span
                      className={cn(
                        "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold",
                        STATUS_COLORS[inv.submission_status] ?? "bg-gray-100 text-gray-800",
                      )}
                    >
                      {t(`status${inv.submission_status.charAt(0)}${inv.submission_status.slice(1).toLowerCase()}`)}
                    </span>
                  </p>
                </div>
              </div>

              {/* Totals */}
              <div className="rounded-lg border p-3">
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">{t("totalExclVat")}</span>
                    <p className="font-mono font-medium">
                      {fmtNumber(inv.total_excluding_vat, locale)} {tc("sar")}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t("totalVat")}</span>
                    <p className="font-mono font-medium">
                      {fmtNumber(inv.total_vat, locale)} {tc("sar")}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t("totalInclVat")}</span>
                    <p className="font-mono font-bold">
                      {fmtNumber(inv.total_including_vat, locale)} {tc("sar")}
                    </p>
                  </div>
                </div>
              </div>

              {/* Buyer info */}
              {inv.buyer_name && (
                <div className="rounded-lg border p-3 text-sm">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-muted-foreground">{t("buyer")}</span>
                      <p className="font-medium">{inv.buyer_name}</p>
                    </div>
                    {inv.buyer_vat_number && (
                      <div>
                        <span className="text-muted-foreground">{t("buyerVat")}</span>
                        <p className="font-mono">{inv.buyer_vat_number}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ZATCA Response */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">{t("zatcaResponse")}</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {inv.zatca_clearance_status && (
                    <div>
                      <span className="text-muted-foreground">{t("clearanceStatus")}</span>
                      <p className="font-medium">{inv.zatca_clearance_status}</p>
                    </div>
                  )}
                  {inv.zatca_reporting_status && (
                    <div>
                      <span className="text-muted-foreground">{t("reportingStatus")}</span>
                      <p className="font-medium">{inv.zatca_reporting_status}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Errors */}
              <div>
                <h3 className="mb-1 text-sm font-semibold text-red-600 dark:text-red-400">
                  {t("errors")}
                </h3>
                {errors.length > 0 ? (
                  <ul className="space-y-1">
                    {errors.map((err, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300"
                      >
                        <XCircle className="mt-0.5 size-4 shrink-0" />
                        {err.message}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">{t("noErrors")}</p>
                )}
              </div>

              {/* Warnings */}
              <div>
                <h3 className="mb-1 text-sm font-semibold text-orange-600 dark:text-orange-400">
                  {t("warnings")}
                </h3>
                {warnings.length > 0 ? (
                  <ul className="space-y-1">
                    {warnings.map((w, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 rounded border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-800 dark:border-orange-800 dark:bg-orange-950/30 dark:text-orange-300"
                      >
                        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                        {w.message}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">{t("noWarnings")}</p>
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            {inv && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownloadXml(inv.invoice_number)}
                >
                  <Download className="mr-1 size-4" />
                  {t("downloadXml")}
                </Button>
                {(inv.submission_status === "PENDING" ||
                  inv.submission_status === "REJECTED") && (
                  <Button
                    size="sm"
                    onClick={() => submitMutation.mutate(inv.invoice_number)}
                    disabled={submitMutation.isPending}
                  >
                    <Send className="mr-1 size-4" />
                    {submitMutation.isPending ? t("submitting") : t("submit")}
                  </Button>
                )}
              </div>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Toast ─────────────────────────────────────────────────────────── */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 ltr:right-6 rtl:left-6 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg",
            toast.type === "success" ? "bg-green-600 text-white" : "bg-red-600 text-white",
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
