"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, RotateCcw, Pencil, ShieldCheck, ShieldOff } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
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

interface UserRow {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
}

type RoleValue = "ADMIN" | "ACCOUNTANT" | "CASHIER";

export default function UsersPage() {
  const t = useTranslations("userManagement");
  const qc = useQueryClient();

  const { data: users, isLoading } = useQuery<UserRow[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/api/v1/users").then((r) => r.data),
  });

  // ── Create user dialog ──
  const [createOpen, setCreateOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<RoleValue>("CASHIER");

  const createMutation = useMutation({
    mutationFn: (body: { username: string; password: string; role: string }) =>
      api.post("/api/v1/users", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setCreateOpen(false);
      setNewUsername("");
      setNewPassword("");
      setNewRole("CASHIER");
    },
  });

  // ── Edit user dialog ──
  const [editOpen, setEditOpen] = useState(false);
  const [editUser, setEditUser] = useState<UserRow | null>(null);
  const [editUsername, setEditUsername] = useState("");
  const [editRole, setEditRole] = useState<RoleValue>("CASHIER");

  const openEdit = (u: UserRow) => {
    setEditUser(u);
    setEditUsername(u.username);
    setEditRole(u.role as RoleValue);
    setEditOpen(true);
  };

  const updateMutation = useMutation({
    mutationFn: (body: { username: string; role: string }) =>
      api.patch(`/api/v1/users/${editUser?.id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setEditOpen(false);
    },
  });

  // ── Toggle active ──
  const toggleMutation = useMutation({
    mutationFn: (userId: string) =>
      api.patch(`/api/v1/users/${userId}/toggle-active`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  // ── Reset password dialog ──
  const [resetOpen, setResetOpen] = useState(false);
  const [resetUserId, setResetUserId] = useState<string>("");
  const [resetNewPw, setResetNewPw] = useState("");

  const resetMutation = useMutation({
    mutationFn: (body: { userId: string; new_password: string }) =>
      api.post(`/api/v1/users/${body.userId}/reset-password`, {
        new_password: body.new_password,
      }),
    onSuccess: () => {
      setResetOpen(false);
      setResetNewPw("");
    },
  });

  const roleLabel = (role: string) => {
    switch (role) {
      case "ADMIN":
        return t("roleAdmin");
      case "ACCOUNTANT":
        return t("roleAccountant");
      case "CASHIER":
        return t("roleCashier");
      default:
        return role;
    }
  };

  if (isLoading) {
    return <p className="text-muted-foreground">{t("loading")}</p>;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          {t("addUser")}
        </Button>
      </div>

      {!users || users.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noUsers")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">
                  {t("username")}
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  {t("role")}
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  {t("status")}
                </th>
                <th className="px-4 py-3 text-right font-medium">
                  {t("actions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-4 py-2.5 font-medium">{u.username}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        "inline-block rounded px-2 py-0.5 text-xs font-semibold",
                        u.role === "ADMIN" &&
                          "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
                        u.role === "ACCOUNTANT" &&
                          "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
                        u.role === "CASHIER" &&
                          "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
                      )}
                    >
                      {roleLabel(u.role)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        "inline-block rounded px-2 py-0.5 text-xs font-semibold",
                        u.is_active
                          ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                          : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
                      )}
                    >
                      {u.is_active ? t("active") : t("inactive")}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={t("editUser")}
                        onClick={() => openEdit(u)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={t("resetPassword")}
                        onClick={() => {
                          setResetUserId(u.id);
                          setResetOpen(true);
                        }}
                      >
                        <RotateCcw className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        title={
                          u.is_active ? t("inactive") : t("active")
                        }
                        onClick={() => toggleMutation.mutate(u.id)}
                      >
                        {u.is_active ? (
                          <ShieldOff className="size-3.5 text-red-500" />
                        ) : (
                          <ShieldCheck className="size-3.5 text-green-500" />
                        )}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create User Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("createUser")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("username")}
              </label>
              <input
                type="text"
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("password")}
              </label>
              <input
                type="password"
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("role")}
              </label>
              <Select
                value={newRole}
                onValueChange={(v) => setNewRole(v as RoleValue)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ADMIN">{t("roleAdmin")}</SelectItem>
                  <SelectItem value="ACCOUNTANT">
                    {t("roleAccountant")}
                  </SelectItem>
                  <SelectItem value="CASHIER">{t("roleCashier")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              disabled={
                createMutation.isPending || !newUsername || !newPassword
              }
              onClick={() =>
                createMutation.mutate({
                  username: newUsername,
                  password: newPassword,
                  role: newRole,
                })
              }
            >
              {createMutation.isPending ? t("creating") : t("createUser")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("editUser")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("username")}
              </label>
              <input
                type="text"
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={editUsername}
                onChange={(e) => setEditUsername(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("role")}
              </label>
              <Select
                value={editRole}
                onValueChange={(v) => setEditRole(v as RoleValue)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ADMIN">{t("roleAdmin")}</SelectItem>
                  <SelectItem value="ACCOUNTANT">
                    {t("roleAccountant")}
                  </SelectItem>
                  <SelectItem value="CASHIER">{t("roleCashier")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              disabled={updateMutation.isPending || !editUsername}
              onClick={() =>
                updateMutation.mutate({
                  username: editUsername,
                  role: editRole,
                })
              }
            >
              {updateMutation.isPending ? t("saving") : t("editUser")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("resetPassword")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("newPassword")}
              </label>
              <input
                type="password"
                className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring"
                value={resetNewPw}
                onChange={(e) => setResetNewPw(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              disabled={resetMutation.isPending || !resetNewPw}
              onClick={() =>
                resetMutation.mutate({
                  userId: resetUserId,
                  new_password: resetNewPw,
                })
              }
            >
              {resetMutation.isPending ? t("resetting") : t("resetPassword")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
