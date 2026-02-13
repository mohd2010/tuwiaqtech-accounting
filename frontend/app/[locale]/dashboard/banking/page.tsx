"use client";

import { useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  Building2,
  Plus,
  Trash2,
  CheckCircle,
  RefreshCcw,
  Link2,
  Unlink,
} from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface StatementLine {
  id: string;
  statement_date: string;
  description: string;
  amount: string;
  reference: string | null;
  status: string;
  matched_split_id: string | null;
  matched_journal_ref: string | null;
  matched_journal_date: string | null;
  reconciled_by: string | null;
  reconciled_at: string | null;
  created_at: string;
}

interface GLSplit {
  split_id: string;
  journal_entry_id: string;
  journal_ref: string | null;
  journal_date: string;
  description: string;
  debit_amount: string;
  credit_amount: string;
  net_amount: string;
}

interface Summary {
  gl_balance: string;
  statement_balance: string;
  reconciled_balance: string;
  unmatched_count: number;
  matched_count: number;
  reconciled_count: number;
}

interface LineInput {
  statement_date: string;
  description: string;
  amount: string;
  reference: string;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function BankingPage() {
  const queryClient = useQueryClient();
  const t = useTranslations("banking");
  const tc = useTranslations("common");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [selectedForReconcile, setSelectedForReconcile] = useState<Set<string>>(new Set());
  const [matchDialog, setMatchDialog] = useState<string | null>(null); // statement_line_id

  // Form state for adding lines
  const [formLines, setFormLines] = useState<LineInput[]>([
    { statement_date: "", description: "", amount: "", reference: "" },
  ]);

  const showToast = useCallback((message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // ─── Queries ────────────────────────────────────────────────────────────

  const { data: summary } = useQuery<Summary>({
    queryKey: ["banking-summary"],
    queryFn: () => api.get("/api/v1/banking/summary").then((r) => r.data),
  });

  const { data: lines = [], isLoading: linesLoading } = useQuery<StatementLine[]>({
    queryKey: ["banking-lines", statusFilter],
    queryFn: () => {
      const params = statusFilter !== "ALL" ? `?status=${statusFilter}` : "";
      return api.get(`/api/v1/banking/statement-lines${params}`).then((r) => r.data);
    },
  });

  const { data: splits = [] } = useQuery<GLSplit[]>({
    queryKey: ["banking-splits"],
    queryFn: () => api.get("/api/v1/banking/unreconciled-splits").then((r) => r.data),
  });

  // ─── Mutations ──────────────────────────────────────────────────────────

  const addLinesMutation = useMutation({
    mutationFn: (data: { lines: LineInput[] }) => api.post("/api/v1/banking/statement-lines", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["banking-summary"] });
      queryClient.invalidateQueries({ queryKey: ["banking-lines"] });
      setFormLines([{ statement_date: "", description: "", amount: "", reference: "" }]);
      setShowEntryForm(false);
      showToast(t("submitSuccess"), "success");
    },
    onError: () => showToast(t("submitFailed"), "error"),
  });

  const autoMatchMutation = useMutation({
    mutationFn: () => api.post("/api/v1/banking/auto-match"),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["banking-summary"] });
      queryClient.invalidateQueries({ queryKey: ["banking-lines"] });
      queryClient.invalidateQueries({ queryKey: ["banking-splits"] });
      showToast(t("autoMatchResult", { count: res.data.matched }), "success");
    },
  });

  const matchMutation = useMutation({
    mutationFn: (data: { statement_line_id: string; split_id: string }) =>
      api.post("/api/v1/banking/match", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["banking-summary"] });
      queryClient.invalidateQueries({ queryKey: ["banking-lines"] });
      queryClient.invalidateQueries({ queryKey: ["banking-splits"] });
      setMatchDialog(null);
    },
    onError: () => showToast(t("matchFailed"), "error"),
  });

  const unmatchMutation = useMutation({
    mutationFn: (id: string) => api.post("/api/v1/banking/unmatch", { statement_line_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["banking-summary"] });
      queryClient.invalidateQueries({ queryKey: ["banking-lines"] });
      queryClient.invalidateQueries({ queryKey: ["banking-splits"] });
    },
    onError: () => showToast(t("unmatchFailed"), "error"),
  });

  const reconcileMutation = useMutation({
    mutationFn: (ids: string[]) =>
      api.post("/api/v1/banking/reconcile", { statement_line_ids: ids }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["banking-summary"] });
      queryClient.invalidateQueries({ queryKey: ["banking-lines"] });
      setSelectedForReconcile(new Set());
      showToast(t("reconcileSuccess"), "success");
    },
    onError: () => showToast(t("reconcileFailed"), "error"),
  });

  // ─── Form helpers ───────────────────────────────────────────────────────

  const addFormLine = () =>
    setFormLines((prev) => [...prev, { statement_date: "", description: "", amount: "", reference: "" }]);

  const removeFormLine = (idx: number) =>
    setFormLines((prev) => prev.filter((_, i) => i !== idx));

  const updateFormLine = (idx: number, field: keyof LineInput, value: string) =>
    setFormLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [field]: value } : l)));

  const handleSubmitLines = () => {
    const validLines = formLines.filter((l) => l.statement_date && l.description && l.amount);
    if (validLines.length === 0) return;
    addLinesMutation.mutate({ lines: validLines });
  };

  const toggleReconcileSelect = (id: string) => {
    setSelectedForReconcile((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      UNMATCHED: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
      MATCHED: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
      RECONCILED: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    };
    return (
      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", colors[status] ?? "")}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="size-7 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
          {([
            ["glBalance", summary.gl_balance],
            ["statementBalance", summary.statement_balance],
            ["reconciledBalance", summary.reconciled_balance],
          ] as const).map(([key, val]) => (
            <div key={key} className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">{t(key)}</p>
              <p className="text-xl font-bold tabular-nums">{Number(val).toLocaleString(undefined, { minimumFractionDigits: 2 })} SAR</p>
            </div>
          ))}
          {([
            ["unreconciled", summary.unmatched_count, "bg-yellow-50 dark:bg-yellow-950/20"],
            ["matched", summary.matched_count, "bg-blue-50 dark:bg-blue-950/20"],
            ["reconciled", summary.reconciled_count, "bg-green-50 dark:bg-green-950/20"],
          ] as const).map(([key, val, bg]) => (
            <div key={key} className={cn("rounded-lg border p-4", bg)}>
              <p className="text-xs text-muted-foreground">{t(key)}</p>
              <p className="text-xl font-bold">{val}</p>
            </div>
          ))}
        </div>
      )}

      {/* Add Statement Lines */}
      <div className="rounded-lg border bg-card">
        <button
          onClick={() => setShowEntryForm(!showEntryForm)}
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold hover:bg-muted/50 transition-colors"
        >
          <span>{t("addStatementLines")}</span>
          <Plus className={cn("size-4 transition-transform", showEntryForm && "rotate-45")} />
        </button>
        {showEntryForm && (
          <div className="border-t px-4 py-3 space-y-3">
            {formLines.map((line, idx) => (
              <div key={idx} className="flex gap-2 items-end">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t("statementDate")}</label>
                  <input
                    type="date"
                    value={line.statement_date}
                    onChange={(e) => updateFormLine(idx, "statement_date", e.target.value)}
                    className="h-9 w-36 rounded-md border bg-background px-2 text-sm"
                  />
                </div>
                <div className="flex-1 space-y-1">
                  <label className="text-xs text-muted-foreground">{t("description")}</label>
                  <input
                    type="text"
                    value={line.description}
                    onChange={(e) => updateFormLine(idx, "description", e.target.value)}
                    className="h-9 w-full rounded-md border bg-background px-2 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t("amount")}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={line.amount}
                    onChange={(e) => updateFormLine(idx, "amount", e.target.value)}
                    placeholder={t("amountHint")}
                    className="h-9 w-32 rounded-md border bg-background px-2 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t("reference")}</label>
                  <input
                    type="text"
                    value={line.reference}
                    onChange={(e) => updateFormLine(idx, "reference", e.target.value)}
                    className="h-9 w-28 rounded-md border bg-background px-2 text-sm"
                  />
                </div>
                {formLines.length > 1 && (
                  <Button size="icon-xs" variant="ghost" onClick={() => removeFormLine(idx)} className="text-destructive">
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            ))}
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={addFormLine}>
                <Plus className="size-3.5 ltr:mr-1 rtl:ml-1" />
                {t("addLine")}
              </Button>
              <Button
                size="sm"
                onClick={handleSubmitLines}
                disabled={addLinesMutation.isPending}
              >
                {addLinesMutation.isPending ? t("submitting") : t("submit")}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Two-panel view */}
      <div className="grid gap-6 xl:grid-cols-2">
        {/* Left: Statement Lines */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h2 className="text-sm font-semibold">{t("statementLines")}</h2>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                onClick={() => autoMatchMutation.mutate()}
                disabled={autoMatchMutation.isPending}
              >
                <RefreshCcw className={cn("size-3.5 ltr:mr-1 rtl:ml-1", autoMatchMutation.isPending && "animate-spin")} />
                {t("autoMatch")}
              </Button>
              {selectedForReconcile.size > 0 && (
                <Button
                  size="sm"
                  onClick={() => reconcileMutation.mutate(Array.from(selectedForReconcile))}
                  disabled={reconcileMutation.isPending}
                >
                  <CheckCircle className="size-3.5 ltr:mr-1 rtl:ml-1" />
                  {t("reconcile")} ({selectedForReconcile.size})
                </Button>
              )}
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex border-b">
            {(["ALL", "UNMATCHED", "MATCHED", "RECONCILED"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={cn(
                  "flex-1 py-2 text-xs font-medium transition-colors",
                  statusFilter === f
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t(`filter${f.charAt(0) + f.slice(1).toLowerCase()}`)}
              </button>
            ))}
          </div>

          <div className="max-h-[500px] overflow-auto">
            {linesLoading ? (
              <p className="p-4 text-sm text-muted-foreground">{t("loading")}</p>
            ) : lines.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">{t("noLines")}</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="p-2 text-left font-medium"></th>
                    <th className="p-2 text-left font-medium">{t("statementDate")}</th>
                    <th className="p-2 text-left font-medium">{t("description")}</th>
                    <th className="p-2 text-right font-medium">{t("amount")}</th>
                    <th className="p-2 text-center font-medium">{t("status")}</th>
                    <th className="p-2 text-right font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr key={line.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="p-2">
                        {line.status === "MATCHED" && (
                          <input
                            type="checkbox"
                            checked={selectedForReconcile.has(line.id)}
                            onChange={() => toggleReconcileSelect(line.id)}
                            className="size-3.5"
                          />
                        )}
                      </td>
                      <td className="p-2">{line.statement_date}</td>
                      <td className="p-2">
                        <span>{line.description}</span>
                        {line.reference && (
                          <span className="ltr:ml-1 rtl:mr-1 text-muted-foreground">({line.reference})</span>
                        )}
                        {line.matched_journal_ref && (
                          <span className="block text-muted-foreground">
                            → {line.matched_journal_ref}
                          </span>
                        )}
                      </td>
                      <td className={cn("p-2 text-right tabular-nums font-medium", Number(line.amount) >= 0 ? "text-green-600" : "text-red-600")}>
                        {Number(line.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="p-2 text-center">{statusBadge(line.status)}</td>
                      <td className="p-2 text-right">
                        <div className="flex justify-end gap-1">
                          {line.status === "UNMATCHED" && (
                            <Button
                              size="icon-xs"
                              variant="outline"
                              onClick={() => setMatchDialog(line.id)}
                              title={t("match")}
                            >
                              <Link2 className="size-3" />
                            </Button>
                          )}
                          {line.status === "MATCHED" && (
                            <Button
                              size="icon-xs"
                              variant="outline"
                              onClick={() => unmatchMutation.mutate(line.id)}
                              title={t("unmatch")}
                            >
                              <Unlink className="size-3" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right: Unreconciled GL Entries */}
        <div className="rounded-lg border bg-card">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold">{t("glEntries")}</h2>
          </div>
          <div className="max-h-[500px] overflow-auto">
            {splits.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">{t("noSplits")}</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="p-2 text-left font-medium">{t("journalRef")}</th>
                    <th className="p-2 text-left font-medium">{t("journalDate")}</th>
                    <th className="p-2 text-left font-medium">{t("description")}</th>
                    <th className="p-2 text-right font-medium">{t("amount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {splits.map((s) => (
                    <tr key={s.split_id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="p-2 font-mono">{s.journal_ref ?? "-"}</td>
                      <td className="p-2">{s.journal_date ? s.journal_date.split("T")[0] : "-"}</td>
                      <td className="p-2">{s.description}</td>
                      <td className={cn("p-2 text-right tabular-nums font-medium", Number(s.net_amount) >= 0 ? "text-green-600" : "text-red-600")}>
                        {Number(s.net_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Manual Match Dialog */}
      {matchDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-lg border bg-card shadow-xl">
            <div className="border-b px-4 py-3">
              <h3 className="text-sm font-semibold">{t("manualMatchTitle")}</h3>
              <p className="text-xs text-muted-foreground">{t("selectEntry")}</p>
            </div>
            <div className="max-h-72 overflow-auto px-4 py-2">
              {splits.length === 0 ? (
                <p className="py-4 text-sm text-muted-foreground">{t("noSplits")}</p>
              ) : (
                <div className="space-y-1">
                  {splits.map((s) => (
                    <button
                      key={s.split_id}
                      onClick={() =>
                        matchMutation.mutate({ statement_line_id: matchDialog, split_id: s.split_id })
                      }
                      className="flex w-full items-center justify-between rounded border px-3 py-2 text-xs hover:bg-muted/50 transition-colors"
                    >
                      <div>
                        <span className="font-mono font-medium">{s.journal_ref ?? "-"}</span>
                        <span className="ltr:ml-2 rtl:mr-2 text-muted-foreground">{s.journal_date ? s.journal_date.split("T")[0] : ""}</span>
                        <span className="ltr:ml-2 rtl:mr-2">{s.description}</span>
                      </div>
                      <span className={cn("font-medium tabular-nums", Number(s.net_amount) >= 0 ? "text-green-600" : "text-red-600")}>
                        {Number(s.net_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end border-t px-4 py-3">
              <Button variant="outline" size="sm" onClick={() => setMatchDialog(null)}>
                {tc("cancel")}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 ltr:right-6 rtl:left-6 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg",
            toast.type === "success" ? "bg-green-600 text-white" : "bg-red-600 text-white",
          )}
        >
          {toast.type === "success" && <CheckCircle className="size-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
}
