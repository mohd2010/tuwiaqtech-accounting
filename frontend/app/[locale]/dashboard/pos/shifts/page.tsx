"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  Clock,
  Plus,
  XCircle,
  CheckCircle,
  AlertCircle,
  Loader2,
  ArrowDown,
  ArrowUp,
  Minus,
} from "lucide-react";
import api from "@/lib/api";
import { fmtDate, fmtTime, fmtNumber } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Register {
  id: string;
  name: string;
  location: string | null;
}

interface ShiftData {
  id: string;
  register_id: string;
  register_name: string;
  user_id: string;
  username: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash: string;
  closing_cash_reported: string | null;
  expected_cash: string | null;
  discrepancy: string | null;
  total_sales: string;
  notes: string | null;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ShiftsPage() {
  const t = useTranslations("shifts");
  const tc = useTranslations("common");
  const locale = useLocale();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const isAdmin = user?.role === "ADMIN" || user?.role === "ACCOUNTANT";

  // ── State ──────────────────────────────────────────────────────────────────
  const [openModal, setOpenModal] = useState(false);
  const [closeModal, setCloseModal] = useState(false);
  const [registerId, setRegisterId] = useState("");
  const [openingCash, setOpeningCash] = useState("");
  const [closingCash, setClosingCash] = useState("");
  const [notes, setNotes] = useState("");

  // Toast
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Queries ──────────────────────────────────────────────────────────────
  const { data: activeShift, isLoading: loadingActive } = useQuery<ShiftData | null>({
    queryKey: ["active-shift"],
    queryFn: () => api.get("/api/v1/pos/shifts/active").then((r) => r.data),
  });

  const { data: registers = [] } = useQuery<Register[]>({
    queryKey: ["registers"],
    queryFn: () => api.get("/api/v1/pos/registers").then((r) => r.data),
  });

  const { data: allShifts = [], isLoading: loadingShifts } = useQuery<ShiftData[]>({
    queryKey: ["all-shifts"],
    queryFn: () => api.get("/api/v1/pos/shifts").then((r) => r.data),
    enabled: isAdmin,
  });

  // ── Mutations ──────────────────────────────────────────────────────────────
  const openMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/pos/shifts/open", {
        register_id: registerId,
        opening_cash: Number(openingCash),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["active-shift"] });
      queryClient.invalidateQueries({ queryKey: ["all-shifts"] });
      setOpenModal(false);
      resetOpenForm();
      showToast(t("openSuccess"), "success");
    },
    onError: () => showToast(t("openFailed"), "error"),
  });

  const closeMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/pos/shifts/${activeShift?.id}/close`, {
        closing_cash_reported: Number(closingCash),
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["active-shift"] });
      queryClient.invalidateQueries({ queryKey: ["all-shifts"] });
      setCloseModal(false);
      resetCloseForm();
      showToast(t("closeSuccess"), "success");
    },
    onError: () => showToast(t("closeFailed"), "error"),
  });

  const resetOpenForm = () => {
    setRegisterId("");
    setOpeningCash("");
  };

  const resetCloseForm = () => {
    setClosingCash("");
    setNotes("");
  };

  const canOpen = registerId && Number(openingCash) >= 0 && openingCash !== "" && !openMutation.isPending;
  const canClose = Number(closingCash) >= 0 && closingCash !== "" && !closeMutation.isPending;

  // ── Helpers ────────────────────────────────────────────────────────────────
  const discrepancyLabel = (disc: string | null) => {
    if (disc === null) return null;
    const n = Number(disc);
    if (n < 0) return { text: t("shortage"), color: "text-red-600 dark:text-red-400", icon: ArrowDown };
    if (n > 0) return { text: t("overage"), color: "text-amber-600 dark:text-amber-400", icon: ArrowUp };
    return { text: t("balanced"), color: "text-green-600 dark:text-green-400", icon: Minus };
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Clock className="size-6 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        {!activeShift && (
          <Button
            onClick={() => {
              resetOpenForm();
              setOpenModal(true);
            }}
          >
            <Plus className="size-4" />
            {t("openShift")}
          </Button>
        )}
      </div>

      {/* Active Shift Card */}
      {loadingActive ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
          <span className="ltr:ml-2 rtl:mr-2 text-sm text-muted-foreground">{t("loading")}</span>
        </div>
      ) : activeShift ? (
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/40 dark:text-green-300">
                {t("open")}
              </span>
              <h2 className="text-lg font-semibold">{t("activeShift")}</h2>
            </div>
            <Button
              variant="destructive"
              onClick={() => {
                resetCloseForm();
                setCloseModal(true);
              }}
            >
              <XCircle className="size-4" />
              {t("closeShift")}
            </Button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">{t("register")}</p>
              <p className="text-sm font-medium">{activeShift.register_name}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t("cashier")}</p>
              <p className="text-sm font-medium">{activeShift.username}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t("openedAt")}</p>
              <p className="text-sm font-medium">
                {fmtDate(activeShift.opened_at, locale)} {fmtTime(activeShift.opened_at, locale)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t("openingCash")}</p>
              <p className="text-sm font-medium tabular-nums">
                {fmtNumber(activeShift.opening_cash, locale)} {tc("sar")}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{t("totalSales")}</p>
              <p className="text-sm font-semibold tabular-nums text-green-600 dark:text-green-400">
                {fmtNumber(activeShift.total_sales, locale)} {tc("sar")}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-8 text-center">
          <Clock className="mx-auto size-10 text-muted-foreground/50 mb-3" />
          <p className="text-sm text-muted-foreground">{t("noActiveShift")}</p>
        </div>
      )}

      {/* Shift History (Admin/Accountant only) */}
      {isAdmin && (
        <>
          <h2 className="text-xl font-semibold">{t("shiftHistory")}</h2>
          <div className="rounded-lg border bg-card">
            {loadingShifts ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
                <span className="ltr:ml-2 rtl:mr-2 text-sm text-muted-foreground">{t("loading")}</span>
              </div>
            ) : allShifts.length === 0 ? (
              <p className="px-4 py-12 text-center text-sm text-muted-foreground">
                {t("noShifts")}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50 text-muted-foreground">
                      <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("cashier")}</th>
                      <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("register")}</th>
                      <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("status")}</th>
                      <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("openedAt")}</th>
                      <th className="px-4 py-3 ltr:text-left rtl:text-right font-semibold">{t("closedAt")}</th>
                      <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("openingCash")}</th>
                      <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("totalSales")}</th>
                      <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("expectedCash")}</th>
                      <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("closingCash")}</th>
                      <th className="px-4 py-3 ltr:text-right rtl:text-left font-semibold">{t("discrepancy")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allShifts.map((shift) => {
                      const disc = discrepancyLabel(shift.discrepancy);
                      return (
                        <tr key={shift.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3">{shift.username}</td>
                          <td className="px-4 py-3">{shift.register_name}</td>
                          <td className="px-4 py-3">
                            <span
                              className={cn(
                                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                                shift.status === "OPEN"
                                  ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                                  : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
                              )}
                            >
                              {shift.status === "OPEN" ? t("open") : t("closed")}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {fmtDate(shift.opened_at, locale)}{" "}
                            <span className="text-xs text-muted-foreground">{fmtTime(shift.opened_at, locale)}</span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {shift.closed_at ? (
                              <>
                                {fmtDate(shift.closed_at, locale)}{" "}
                                <span className="text-xs text-muted-foreground">{fmtTime(shift.closed_at, locale)}</span>
                              </>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums">
                            {fmtNumber(shift.opening_cash, locale)}
                          </td>
                          <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums font-medium text-green-600 dark:text-green-400">
                            {fmtNumber(shift.total_sales, locale)}
                          </td>
                          <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums">
                            {shift.expected_cash ? fmtNumber(shift.expected_cash, locale) : "—"}
                          </td>
                          <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums">
                            {shift.closing_cash_reported ? fmtNumber(shift.closing_cash_reported, locale) : "—"}
                          </td>
                          <td className="px-4 py-3 ltr:text-right rtl:text-left tabular-nums">
                            {disc ? (
                              <span className={cn("inline-flex items-center gap-1 font-semibold", disc.color)}>
                                <disc.icon className="size-3.5" />
                                {fmtNumber(Math.abs(Number(shift.discrepancy)), locale)}
                                <span className="text-xs font-normal">({disc.text})</span>
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Open Shift Dialog ──────────────────────────────────────────────── */}
      <Dialog open={openModal} onOpenChange={setOpenModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("openShift")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Register */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("register")}</label>
              <select
                value={registerId}
                onChange={(e) => setRegisterId(e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">{t("selectRegister")}</option>
                {registers.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}{r.location ? ` — ${r.location}` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Opening Cash */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("openingCash")}</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={openingCash}
                onChange={(e) => setOpeningCash(e.target.value)}
                placeholder="0.00"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm tabular-nums placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpenModal(false)}>
              {tc("cancel")}
            </Button>
            <Button disabled={!canOpen} onClick={() => openMutation.mutate()}>
              {openMutation.isPending ? t("opening") : t("openShift")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Close Shift Dialog ─────────────────────────────────────────────── */}
      <Dialog open={closeModal} onOpenChange={setCloseModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("closeShift")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Shift Summary */}
            {activeShift && (
              <div className="rounded-md bg-muted/50 p-4 space-y-2">
                <h3 className="text-sm font-semibold">{t("shiftSummary")}</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">{t("register")}:</span>{" "}
                    {activeShift.register_name}
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t("openingCash")}:</span>{" "}
                    <span className="tabular-nums">{fmtNumber(activeShift.opening_cash, locale)} {tc("sar")}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t("totalSales")}:</span>{" "}
                    <span className="tabular-nums font-medium text-green-600 dark:text-green-400">
                      {fmtNumber(activeShift.total_sales, locale)} {tc("sar")}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Closing Cash */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("closingCash")}</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={closingCash}
                onChange={(e) => setClosingCash(e.target.value)}
                placeholder="0.00"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm tabular-nums placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("notes")}</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("notesPlaceholder")}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCloseModal(false)}>
              {tc("cancel")}
            </Button>
            <Button variant="destructive" disabled={!canClose} onClick={() => closeMutation.mutate()}>
              {closeMutation.isPending ? t("closing") : t("closeShift")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Toast ──────────────────────────────────────────────────────────── */}
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
