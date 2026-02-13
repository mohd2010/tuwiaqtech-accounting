"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  Landmark,
  Plus,
  Lock,
  Pencil,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";
import { fmtNumber } from "@/lib/format";
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

type AccountType = "ASSET" | "LIABILITY" | "EQUITY" | "REVENUE" | "EXPENSE";

interface AccountFull {
  id: string;
  code: string;
  name: string;
  account_type: AccountType;
  parent_id: string | null;
  is_active: boolean;
  is_system: boolean;
  balance: string;
  created_at: string;
}

// ─── Color mapping ──────────────────────────────────────────────────────────

const TYPE_COLORS: Record<AccountType, { bg: string; text: string; border: string }> = {
  ASSET: { bg: "bg-blue-50 dark:bg-blue-950/30", text: "text-blue-700 dark:text-blue-300", border: "border-blue-200 dark:border-blue-800" },
  LIABILITY: { bg: "bg-amber-50 dark:bg-amber-950/30", text: "text-amber-700 dark:text-amber-300", border: "border-amber-200 dark:border-amber-800" },
  EQUITY: { bg: "bg-purple-50 dark:bg-purple-950/30", text: "text-purple-700 dark:text-purple-300", border: "border-purple-200 dark:border-purple-800" },
  REVENUE: { bg: "bg-green-50 dark:bg-green-950/30", text: "text-green-700 dark:text-green-300", border: "border-green-200 dark:border-green-800" },
  EXPENSE: { bg: "bg-red-50 dark:bg-red-950/30", text: "text-red-700 dark:text-red-300", border: "border-red-200 dark:border-red-800" },
};

const TYPE_LABEL_KEY: Record<AccountType, string> = {
  ASSET: "assets",
  LIABILITY: "liabilities",
  EQUITY: "equity",
  REVENUE: "revenue",
  EXPENSE: "expenses",
};

const BALANCE_SHEET_TYPES: AccountType[] = ["ASSET", "LIABILITY", "EQUITY"];
const PNL_TYPES: AccountType[] = ["REVENUE", "EXPENSE"];
const ALL_TYPES: AccountType[] = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"];

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AccountsPage() {
  const t = useTranslations("accounts");
  const tFin = useTranslations("FinancialData");
  const tc = useTranslations("common");
  const locale = useLocale();
  const queryClient = useQueryClient();

  // ── State ──────────────────────────────────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<AccountFull | null>(null);

  // Create form
  const [newType, setNewType] = useState<AccountType>("ASSET");
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");

  // Edit form
  const [editName, setEditName] = useState("");
  const [editActive, setEditActive] = useState(true);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: accounts = [], isLoading } = useQuery<AccountFull[]>({
    queryKey: ["accounts-full"],
    queryFn: () => api.get("/api/v1/accounts").then((r) => r.data),
  });

  const { data: suggestedCode } = useQuery<{ code: string }>({
    queryKey: ["next-code", newType],
    queryFn: () => api.get(`/api/v1/accounts/next-code?account_type=${newType}`).then((r) => r.data),
    enabled: createOpen,
  });

  useEffect(() => {
    if (suggestedCode?.code) {
      setNewCode(suggestedCode.code);
    }
  }, [suggestedCode]);

  // ── Mutations ──────────────────────────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/accounts", {
        code: newCode,
        name: newName,
        account_type: newType,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts-full"] });
      setCreateOpen(false);
      setNewName("");
      setNewCode("");
      showToast(t("createSuccess"), "success");
    },
    onError: () => showToast(t("createFailed"), "error"),
  });

  const editMutation = useMutation({
    mutationFn: () =>
      api.patch(`/api/v1/accounts/${selectedAccount!.id}`, {
        name: editName,
        is_active: editActive,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts-full"] });
      setEditOpen(false);
      showToast(t("editSuccess"), "success");
    },
    onError: () => showToast(t("editFailed"), "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/api/v1/accounts/${selectedAccount!.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts-full"] });
      setDeleteOpen(false);
      showToast(t("deleteSuccess"), "success");
    },
    onError: () => showToast(t("deleteFailed"), "error"),
  });

  // ── Helpers ────────────────────────────────────────────────────────────────
  const groupedByType = (types: AccountType[]) =>
    types.map((type) => ({
      type,
      accounts: accounts.filter((a) => a.account_type === type),
    }));

  const openEdit = (account: AccountFull) => {
    setSelectedAccount(account);
    setEditName(account.name);
    setEditActive(account.is_active);
    setEditOpen(true);
  };

  const openDelete = (account: AccountFull) => {
    setSelectedAccount(account);
    setDeleteOpen(true);
  };

  const openCreate = () => {
    setNewType("ASSET");
    setNewName("");
    setNewCode("");
    setCreateOpen(true);
  };

  const canCreate = newCode.trim().length >= 4 && newName.trim().length > 0 && !createMutation.isPending;

  // ── Render helpers ─────────────────────────────────────────────────────────

  const renderTypeGroup = (type: AccountType, groupAccounts: AccountFull[]) => {
    const colors = TYPE_COLORS[type];
    return (
      <div key={type} className={cn("rounded-lg border overflow-hidden", colors.border)}>
        <div className={cn("px-4 py-2.5 font-semibold text-sm", colors.bg, colors.text)}>
          {t(TYPE_LABEL_KEY[type])}
        </div>
        {groupAccounts.length === 0 ? (
          <div className="px-4 py-4 text-sm text-muted-foreground">{t("noAccounts")}</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="px-4 py-2 ltr:text-left rtl:text-right font-semibold w-24">{t("code")}</th>
                <th className="px-4 py-2 ltr:text-left rtl:text-right font-semibold">{t("name")}</th>
                <th className="px-4 py-2 ltr:text-right rtl:text-left font-semibold w-40">{t("balance")}</th>
                <th className="px-4 py-2 ltr:text-left rtl:text-right font-semibold w-28">{t("status")}</th>
                <th className="px-4 py-2 w-24" />
              </tr>
            </thead>
            <tbody>
              {groupAccounts.map((account) => (
                <tr key={account.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="px-4 py-2.5 font-mono text-xs">{account.code}</td>
                  <td className="px-4 py-2.5">
                    {account.is_system ? tFin(account.name) : account.name}
                  </td>
                  <td className="px-4 py-2.5 ltr:text-right rtl:text-left tabular-nums font-medium">
                    {fmtNumber(account.balance, locale)} {tc("sar")}
                  </td>
                  <td className="px-4 py-2.5">
                    {account.is_system ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
                        <Lock className="size-3" />
                        {t("system")}
                      </span>
                    ) : account.is_active ? (
                      <span className="inline-flex items-center rounded-full bg-green-100 dark:bg-green-900/40 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-300">
                        {t("active")}
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                        {t("inactive")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {!account.is_system && (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => openEdit(account)}
                          title={t("edit")}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => openDelete(account)}
                          title={t("delete")}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  };

  // ── Main render ────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
        <span className="ltr:ml-2 rtl:mr-2 text-sm text-muted-foreground">{t("loading")}</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Landmark className="size-6 text-primary" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t("addAccount")}
        </Button>
      </div>

      {/* Balance Sheet Accounts */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground border-b pb-2">
          {t("balanceSheet")}
        </h2>
        <div className="space-y-4">
          {groupedByType(BALANCE_SHEET_TYPES).map(({ type, accounts: accts }) =>
            renderTypeGroup(type, accts)
          )}
        </div>
      </div>

      {/* Profit & Loss Accounts */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground border-b pb-2">
          {t("profitAndLoss")}
        </h2>
        <div className="space-y-4">
          {groupedByType(PNL_TYPES).map(({ type, accounts: accts }) =>
            renderTypeGroup(type, accts)
          )}
        </div>
      </div>

      {/* ── Create Account Dialog ─────────────────────────────────────────── */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("createTitle")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Type */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("accountType")}</label>
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value as AccountType)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {ALL_TYPES.map((at) => (
                  <option key={at} value={at}>
                    {tFin(at)}
                  </option>
                ))}
              </select>
            </div>

            {/* Code */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("accountCode")}</label>
              <input
                type="text"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder={suggestedCode?.code ?? ""}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {suggestedCode?.code && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("suggestedCode")}: {suggestedCode.code}
                </p>
              )}
            </div>

            {/* Name */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t("accountName")}</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button disabled={!canCreate} onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? t("creating") : tc("create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Edit Account Dialog ───────────────────────────────────────────── */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("editTitle")}</DialogTitle>
          </DialogHeader>
          {selectedAccount && (
            <div className="space-y-4 py-2">
              {/* Code (read-only) */}
              <div>
                <label className="mb-1 block text-sm font-medium">{t("accountCode")}</label>
                <input
                  type="text"
                  value={selectedAccount.code}
                  disabled
                  className="h-10 w-full rounded-md border bg-muted px-3 text-sm font-mono"
                />
              </div>

              {/* Type (read-only) */}
              <div>
                <label className="mb-1 block text-sm font-medium">{t("accountType")}</label>
                <input
                  type="text"
                  value={tFin(selectedAccount.account_type)}
                  disabled
                  className="h-10 w-full rounded-md border bg-muted px-3 text-sm"
                />
              </div>

              {/* Name */}
              <div>
                <label className="mb-1 block text-sm font-medium">{t("accountName")}</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              {/* Active toggle */}
              <div className="flex items-center gap-3">
                <label className="text-sm font-medium">{t("status")}</label>
                <button
                  type="button"
                  onClick={() => setEditActive(!editActive)}
                  className={cn(
                    "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
                    editActive ? "bg-primary" : "bg-gray-300 dark:bg-gray-600",
                  )}
                >
                  <span
                    className={cn(
                      "pointer-events-none inline-block size-5 rounded-full bg-white shadow-lg transform transition-transform",
                      editActive ? "ltr:translate-x-5 rtl:-translate-x-5" : "translate-x-0",
                    )}
                  />
                </button>
                <span className="text-sm text-muted-foreground">
                  {editActive ? t("active") : t("inactive")}
                </span>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button
              disabled={!editName.trim() || editMutation.isPending}
              onClick={() => editMutation.mutate()}
            >
              {editMutation.isPending ? t("creating") : tc("save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete Confirmation Dialog ────────────────────────────────────── */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tc("delete")}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground py-2">
            {t("deleteConfirm")}
          </p>
          {selectedAccount && (
            <p className="text-sm font-medium">
              {selectedAccount.code} &mdash; {selectedAccount.name}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              {deleteMutation.isPending ? tc("loading") : tc("delete")}
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
