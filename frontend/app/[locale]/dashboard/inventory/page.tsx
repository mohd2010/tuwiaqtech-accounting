"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { Plus, PackagePlus, Printer } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StockInDialog } from "@/components/inventory/StockInDialog";
import { BarcodePrintDialog } from "@/components/inventory/BarcodePrintDialog";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Category {
  id: string;
  name: string;
  description: string | null;
}

interface Product {
  id: string;
  name: string;
  sku: string;
  category_id: string;
  description: string | null;
  unit_price: string;
  cost_price: string;
  current_stock: number;
  reorder_level: number;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function InventoryPage() {
  const queryClient = useQueryClient();
  const t = useTranslations("inventory");
  const tc = useTranslations("common");
  const [showModal, setShowModal] = useState(false);
  const [stockInProduct, setStockInProduct] = useState<Product | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [printProducts, setPrintProducts] = useState<Product[]>([]);

  const { data: products = [], isLoading } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: () => api.get("/api/v1/inventory/products").then((r) => r.data),
  });

  const { data: categories = [] } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: () => api.get("/api/v1/inventory/categories").then((r) => r.data),
  });

  const categoryMap = Object.fromEntries(
    categories.map((c) => [c.id, c.name]),
  );

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <div className="flex gap-2">
          {selectedIds.size > 0 && (
            <Button
              variant="outline"
              onClick={() => {
                const selected = products.filter((p) => selectedIds.has(p.id));
                setPrintProducts(selected);
              }}
            >
              <Printer className="size-4" />
              {t("printLabels")} ({selectedIds.size})
            </Button>
          )}
          <Button onClick={() => setShowModal(true)}>
            <Plus className="size-4" />
            {t("addProduct")}
          </Button>
        </div>
      </div>

      {/* Product Table */}
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="w-10 px-4 py-3">
                <input
                  type="checkbox"
                  className="rounded border-gray-300"
                  checked={products.length > 0 && selectedIds.size === products.length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedIds(new Set(products.map((p) => p.id)));
                    } else {
                      setSelectedIds(new Set());
                    }
                  }}
                />
              </th>
              <th className="px-4 py-3 text-left font-medium">{t("sku")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("name")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("category")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("stock")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("unitPrice")}</th>
              <th className="px-4 py-3 text-right font-medium">{tc("actions")}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  {tc("loading")}
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  {t("noProducts")}
                </td>
              </tr>
            ) : (
              products.map((p) => (
                <tr key={p.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300"
                      checked={selectedIds.has(p.id)}
                      onChange={(e) => {
                        const next = new Set(selectedIds);
                        if (e.target.checked) {
                          next.add(p.id);
                        } else {
                          next.delete(p.id);
                        }
                        setSelectedIds(next);
                      }}
                    />
                  </td>
                  <td className="px-4 py-3 font-mono">{p.sku}</td>
                  <td className="px-4 py-3">{p.name}</td>
                  <td className="px-4 py-3">{categoryMap[p.category_id] ?? "—"}</td>
                  <td
                    className={cn(
                      "px-4 py-3 text-right font-semibold",
                      p.current_stock <= p.reorder_level
                        ? "text-red-600"
                        : "text-foreground",
                    )}
                  >
                    {p.current_stock}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {Number(p.unit_price).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right flex gap-1 justify-end">
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => setPrintProducts([p])}
                      title={t("printLabel")}
                    >
                      <Printer className="size-3" />
                    </Button>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => setStockInProduct(p)}
                    >
                      <PackagePlus className="size-3" />
                      {t("restock")}
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add Product Modal */}
      {showModal && (
        <AddProductModal
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["products"] });
            setShowModal(false);
          }}
        />
      )}

      {/* Stock In Dialog */}
      {stockInProduct && (
        <StockInDialog
          productId={stockInProduct.id}
          productName={stockInProduct.name}
          onClose={() => setStockInProduct(null)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["products"] });
            setStockInProduct(null);
          }}
        />
      )}

      {/* Barcode Print Dialog */}
      {printProducts.length > 0 && (
        <BarcodePrintDialog
          products={printProducts}
          onClose={() => {
            setPrintProducts([]);
            setSelectedIds(new Set());
          }}
        />
      )}
    </div>
  );
}

// ─── Add Product Modal ───────────────────────────────────────────────────────

function AddProductModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const t = useTranslations("inventory");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [apiError, setApiError] = useState("");

  const { data: categories = [] } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: () => api.get("/api/v1/inventory/categories").then((r) => r.data),
  });
  const [showNewCategory, setShowNewCategory] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [creatingCategory, setCreatingCategory] = useState(false);

  const addProductSchema = z.object({
    name: z.string().min(1, t("required")),
    sku: z.string().min(1, t("required")),
    category_id: z.string().min(1, t("selectCategory")),
    unit_price: z.number().min(0, "Must be >= 0"),
    cost_price: z.number().min(0, "Must be >= 0"),
    reorder_level: z.number().int().min(0, "Must be >= 0"),
  });

  type AddProductForm = z.infer<typeof addProductSchema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AddProductForm>({
    resolver: zodResolver(addProductSchema),
    defaultValues: { reorder_level: 0 },
  });

  const mutation = useMutation({
    mutationFn: (data: AddProductForm) =>
      api.post("/api/v1/inventory/products", data),
    onSuccess,
    onError: () => setApiError("Failed to create product."),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">{t("addProduct")}</h2>

        <form
          onSubmit={handleSubmit((data) => mutation.mutate(data))}
          className="space-y-3"
        >
          <Field label={t("name")} error={errors.name?.message}>
            <input
              {...register("name")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </Field>

          <Field label={t("sku")} error={errors.sku?.message}>
            <input
              {...register("sku")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </Field>

          <Field label={t("category")} error={errors.category_id?.message}>
            <select
              {...register("category_id")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">{tc("select")}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {!showNewCategory ? (
              <button
                type="button"
                onClick={() => setShowNewCategory(true)}
                className="mt-1 text-xs text-primary hover:underline"
              >
                + {t("newCategory")}
              </button>
            ) : (
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={newCategoryName}
                  onChange={(e) => setNewCategoryName(e.target.value)}
                  placeholder={t("categoryName")}
                  className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
                <Button
                  type="button"
                  size="sm"
                  disabled={!newCategoryName.trim() || creatingCategory}
                  onClick={async () => {
                    setCreatingCategory(true);
                    try {
                      await api.post("/api/v1/inventory/categories", {
                        name: newCategoryName.trim(),
                      });
                      await queryClient.invalidateQueries({ queryKey: ["categories"] });
                      setNewCategoryName("");
                      setShowNewCategory(false);
                    } catch {
                      setApiError("Failed to create category.");
                    } finally {
                      setCreatingCategory(false);
                    }
                  }}
                >
                  {t("addCategory")}
                </Button>
              </div>
            )}
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={t("costPrice")} error={errors.cost_price?.message}>
              <input
                type="number"
                step="0.01"
                {...register("cost_price", { valueAsNumber: true })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </Field>
            <Field label={t("unitPrice")} error={errors.unit_price?.message}>
              <input
                type="number"
                step="0.01"
                {...register("unit_price", { valueAsNumber: true })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </Field>
          </div>

          <Field label={t("reorderLevel")} error={errors.reorder_level?.message}>
            <input
              type="number"
              {...register("reorder_level", { valueAsNumber: true })}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </Field>

          {apiError && (
            <p className="text-center text-sm text-red-500">{apiError}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {tc("cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("creating") : t("createProduct")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Field helper ────────────────────────────────────────────────────────────

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium">{label}</label>
      {children}
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}
