"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Banknote } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import PaymentDialog from "@/components/suppliers/PaymentDialog";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Supplier {
  id: string;
  name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  vat_number: string | null;
  address: string | null;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function SuppliersPage() {
  const queryClient = useQueryClient();
  const t = useTranslations("suppliers");
  const tc = useTranslations("common");
  const [showForm, setShowForm] = useState(false);
  const [paySupplier, setPaySupplier] = useState<Supplier | null>(null);

  const { data: suppliers = [], isLoading } = useQuery<Supplier[]>({
    queryKey: ["suppliers"],
    queryFn: () => api.get("/api/v1/suppliers/").then((r) => r.data),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="size-4" />
          {t("addSupplier")}
        </Button>
      </div>

      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("name")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("contact")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("email")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("phone")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("vatNumber")}</th>
              <th className="px-4 py-3 text-right font-medium">{tc("actions")}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  {tc("loading")}
                </td>
              </tr>
            ) : suppliers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  {t("noSuppliers")}
                </td>
              </tr>
            ) : (
              suppliers.map((s) => (
                <tr key={s.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{s.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.contact_person ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.email ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.phone ?? "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {s.vat_number ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => setPaySupplier(s)}
                    >
                      <Banknote className="size-3" />
                      {t("pay")}
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <AddSupplierDialog
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["suppliers"] });
            setShowForm(false);
          }}
        />
      )}

      {paySupplier && (
        <PaymentDialog
          supplierId={paySupplier.id}
          supplierName={paySupplier.name}
          onClose={() => setPaySupplier(null)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["supplier-balance"] });
            setPaySupplier(null);
          }}
        />
      )}
    </div>
  );
}

// ─── Add Supplier Dialog ─────────────────────────────────────────────────────

function AddSupplierDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const t = useTranslations("suppliers");
  const tc = useTranslations("common");
  const [form, setForm] = useState({
    name: "",
    contact_person: "",
    email: "",
    phone: "",
    vat_number: "",
    address: "",
  });
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: () => api.post("/api/v1/suppliers/", form),
    onSuccess,
    onError: () => setError(t("failedCreate")),
  });

  const set = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("addSupplier")}</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-3"
        >
          <Field label={t("companyName")}>
            <input
              required
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={t("contactPerson")}>
              <input
                value={form.contact_person}
                onChange={(e) => set("contact_person", e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </Field>
            <Field label={t("phone")}>
              <input
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label={t("email")}>
              <input
                type="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </Field>
            <Field label={t("vatNumber")}>
              <input
                value={form.vat_number}
                onChange={(e) => set("vat_number", e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </Field>
          </div>

          <Field label={t("address")}>
            <textarea
              rows={2}
              value={form.address}
              onChange={(e) => set("address", e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </Field>

          {error && (
            <p className="text-center text-sm text-red-500">{error}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {tc("cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("saving") : t("addSupplier")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─── Field helper ────────────────────────────────────────────────────────────

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium">{label}</label>
      {children}
    </div>
  );
}
