"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import { Plus, Play, Pause, Pencil, Trash2, X } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ─── Types ───────────────────────────────────────────────────────────────────

interface RecurringListItem {
  id: string;
  name: string;
  description: string;
  frequency: string;
  next_run_date: string;
  end_date: string | null;
  status: string;
  total_posted: number;
  is_due: boolean;
  split_count: number;
}

interface SplitDetail {
  id: string;
  account_id: string;
  account_code: string;
  account_name: string;
  debit_amount: string;
  credit_amount: string;
}

interface RecurringDetail {
  id: string;
  name: string;
  description: string;
  reference_prefix: string | null;
  frequency: string;
  next_run_date: string;
  end_date: string | null;
  status: string;
  last_posted_at: string | null;
  total_posted: number;
  splits: SplitDetail[];
}

interface AccountOption {
  id: string;
  code: string;
  name: string;
}

interface FormSplit {
  account_id: string;
  amount: string;
  type: "debit" | "credit";
}

// ─── Frequency helpers ──────────────────────────────────────────────────────

const FREQUENCIES = ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUALLY"] as const;

function freqLabel(freq: string, t: ReturnType<typeof useTranslations>): string {
  const map: Record<string, string> = {
    DAILY: t("freqDaily"),
    WEEKLY: t("freqWeekly"),
    MONTHLY: t("freqMonthly"),
    QUARTERLY: t("freqQuarterly"),
    ANNUALLY: t("freqAnnually"),
  };
  return map[freq] ?? freq;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function RecurringPage() {
  const t = useTranslations("recurring");
  const tc = useTranslations("common");
  const tData = useTranslations("FinancialData");
  const locale = useLocale();
  const qc = useQueryClient();

  // ── Queries ──
  const { data: entries = [], isLoading } = useQuery<RecurringListItem[]>({
    queryKey: ["recurring-entries"],
    queryFn: () => api.get("/api/v1/recurring-entries").then((r) => r.data),
  });

  const { data: accounts = [] } = useQuery<AccountOption[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/journal/accounts").then((r) => r.data),
  });

  // ── Form state ──
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formRefPrefix, setFormRefPrefix] = useState("");
  const [formFreq, setFormFreq] = useState("MONTHLY");
  const [formNextDate, setFormNextDate] = useState("");
  const [formEndDate, setFormEndDate] = useState("");
  const [formSplits, setFormSplits] = useState<FormSplit[]>([
    { account_id: "", amount: "", type: "debit" },
    { account_id: "", amount: "", type: "credit" },
  ]);
  const [formError, setFormError] = useState("");

  const resetForm = () => {
    setEditId(null);
    setFormName("");
    setFormDesc("");
    setFormRefPrefix("");
    setFormFreq("MONTHLY");
    setFormNextDate("");
    setFormEndDate("");
    setFormSplits([
      { account_id: "", amount: "", type: "debit" },
      { account_id: "", amount: "", type: "credit" },
    ]);
    setFormError("");
  };

  const openCreate = () => {
    resetForm();
    setDialogOpen(true);
  };

  const openEdit = async (id: string) => {
    try {
      const resp = await api.get<RecurringDetail>(`/api/v1/recurring-entries/${id}`);
      const d = resp.data;
      setEditId(id);
      setFormName(d.name);
      setFormDesc(d.description);
      setFormRefPrefix(d.reference_prefix ?? "");
      setFormFreq(d.frequency);
      setFormNextDate(d.next_run_date);
      setFormEndDate(d.end_date ?? "");
      setFormSplits(
        d.splits.map((s) => ({
          account_id: s.account_id,
          amount: Number(s.debit_amount) > 0 ? s.debit_amount : s.credit_amount,
          type: (Number(s.debit_amount) > 0 ? "debit" : "credit") as "debit" | "credit",
        })),
      );
      setFormError("");
      setDialogOpen(true);
    } catch {
      // ignore
    }
  };

  // ── Computed balance ──
  const totalDebits = formSplits
    .filter((s) => s.type === "debit")
    .reduce((sum, s) => sum + (parseFloat(s.amount) || 0), 0);
  const totalCredits = formSplits
    .filter((s) => s.type === "credit")
    .reduce((sum, s) => sum + (parseFloat(s.amount) || 0), 0);
  const isBalanced = totalDebits > 0 && totalDebits === totalCredits;

  // ── Mutations ──
  const createMutation = useMutation({
    mutationFn: (body: object) => api.post("/api/v1/recurring-entries", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurring-entries"] });
      setDialogOpen(false);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Error");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.put(`/api/v1/recurring-entries/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurring-entries"] });
      setDialogOpen(false);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Error");
    },
  });

  const postMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/recurring-entries/${id}/post`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recurring-entries"] }),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/api/v1/recurring-entries/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recurring-entries"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/recurring-entries/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recurring-entries"] }),
  });

  const handleSubmit = () => {
    const payload = {
      name: formName,
      description: formDesc,
      reference_prefix: formRefPrefix || null,
      frequency: formFreq,
      next_run_date: formNextDate,
      end_date: formEndDate || null,
      splits: formSplits.map((s) => ({
        account_id: s.account_id,
        amount: s.amount,
        type: s.type,
      })),
    };
    if (editId) {
      updateMutation.mutate({ id: editId, body: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const updateSplit = (idx: number, field: keyof FormSplit, value: string) => {
    setFormSplits((prev) =>
      prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)),
    );
  };

  const removeSplit = (idx: number) => {
    setFormSplits((prev) => prev.filter((_, i) => i !== idx));
  };

  const addSplit = () => {
    setFormSplits((prev) => [...prev, { account_id: "", amount: "", type: "debit" }]);
  };

  const accountLabel = (id: string) => {
    const a = accounts.find((ac) => ac.id === id);
    if (!a) return id;
    const name = tData.has(a.name) ? tData(a.name) : a.name;
    return `${a.code} - ${name}`;
  };

  if (isLoading) {
    return <p className="text-muted-foreground">{t("loading")}</p>;
  }

  const canSubmit =
    formName && formDesc && formNextDate && isBalanced &&
    formSplits.every((s) => s.account_id && s.amount) &&
    !(createMutation.isPending || updateMutation.isPending);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t("newEntry")}
        </Button>
      </div>

      {entries.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noEntries")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("name")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("frequency")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("nextRunDate")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("status")}</th>
                <th className="px-4 py-3 text-center font-medium">{t("timesPosted")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr
                  key={e.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-4 py-2.5">
                    <div className="font-medium">{e.name}</div>
                    <div className="text-xs text-muted-foreground">{e.description}</div>
                  </td>
                  <td className="px-4 py-2.5">{freqLabel(e.frequency, t)}</td>
                  <td className="px-4 py-2.5">
                    <span>{fmtDate(e.next_run_date, locale)}</span>
                    {e.is_due && (
                      <span className="ltr:ml-2 rtl:mr-2 inline-block rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-300">
                        {t("due")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        "inline-block rounded px-2 py-0.5 text-xs font-semibold",
                        e.status === "ACTIVE"
                          ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                          : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
                      )}
                    >
                      {e.status === "ACTIVE" ? t("active") : t("paused")}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">{e.total_posted}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={t("postNow")}
                        disabled={!e.is_due || postMutation.isPending}
                        onClick={() => postMutation.mutate(e.id)}
                      >
                        <Play className="size-3.5 text-green-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={e.status === "ACTIVE" ? t("pause") : t("resume")}
                        onClick={() =>
                          statusMutation.mutate({
                            id: e.id,
                            status: e.status === "ACTIVE" ? "PAUSED" : "ACTIVE",
                          })
                        }
                      >
                        <Pause className={cn("size-3.5", e.status === "ACTIVE" ? "text-yellow-600" : "text-green-600")} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={t("editEntry")}
                        onClick={() => openEdit(e.id)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={tc("delete")}
                        onClick={() => {
                          if (window.confirm(t("deleteConfirm"))) {
                            deleteMutation.mutate(e.id);
                          }
                        }}
                      >
                        <Trash2 className="size-3.5 text-red-500" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editId ? t("editEntry") : t("newEntry")}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Name */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("name")}</label>
              <input
                type="text"
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("description")}</label>
              <input
                type="text"
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
              />
            </div>

            {/* Reference Prefix + Frequency row */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">{t("referencePrefix")}</label>
                <input
                  type="text"
                  className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("referencePrefixPlaceholder")}
                  value={formRefPrefix}
                  onChange={(e) => setFormRefPrefix(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">{t("frequency")}</label>
                <Select value={formFreq} onValueChange={setFormFreq}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FREQUENCIES.map((f) => (
                      <SelectItem key={f} value={f}>
                        {freqLabel(f, t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Dates row */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">{t("nextRunDate")}</label>
                <input
                  type="date"
                  className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                  value={formNextDate}
                  onChange={(e) => setFormNextDate(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">{t("endDateOptional")}</label>
                <input
                  type="date"
                  className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                  value={formEndDate}
                  onChange={(e) => setFormEndDate(e.target.value)}
                />
              </div>
            </div>

            {/* Splits */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium">{t("splits")}</label>
                <Button variant="outline" size="sm" onClick={addSplit}>
                  <Plus className="size-3" />
                  {t("addSplit")}
                </Button>
              </div>

              <div className="space-y-2">
                {formSplits.map((s, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Select
                      value={s.account_id}
                      onValueChange={(v) => updateSplit(idx, "account_id", v)}
                    >
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder={t("selectAccount")} />
                      </SelectTrigger>
                      <SelectContent>
                        {accounts.map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.code} - {tData.has(a.name) ? tData(a.name) : a.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="flex h-9 w-28 rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                      placeholder={t("amount")}
                      value={s.amount}
                      onChange={(e) => updateSplit(idx, "amount", e.target.value)}
                    />
                    <Select
                      value={s.type}
                      onValueChange={(v) => updateSplit(idx, "type", v)}
                    >
                      <SelectTrigger className="w-24">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="debit">{t("debit")}</SelectItem>
                        <SelectItem value="credit">{t("credit")}</SelectItem>
                      </SelectContent>
                    </Select>
                    {formSplits.length > 2 && (
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => removeSplit(idx)}
                      >
                        <X className="size-3.5 text-red-500" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>

              {/* Balance indicator */}
              <div className="mt-2 flex items-center gap-4 text-xs">
                <span>
                  {t("totalDebits")}: {totalDebits.toFixed(2)}
                </span>
                <span>
                  {t("totalCredits")}: {totalCredits.toFixed(2)}
                </span>
                <span
                  className={cn(
                    "font-semibold",
                    isBalanced ? "text-green-600" : "text-red-600",
                  )}
                >
                  {isBalanced ? t("balanced") : t("unbalanced")}
                </span>
              </div>
            </div>

            {formError && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200">
                {formError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button disabled={!canSubmit} onClick={handleSubmit}>
              {createMutation.isPending || updateMutation.isPending
                ? editId
                  ? t("saving")
                  : t("creating")
                : editId
                  ? tc("save")
                  : tc("create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
