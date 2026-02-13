"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import api from "@/lib/api";
import { fmtNumber } from "@/lib/format";
import ExportButton from "@/components/reports/ExportButton";

interface ValuationItem {
  product_id: string;
  sku: string;
  name: string;
  category: string;
  quantity: number;
  cost_price: string;
  total_value: string;
}

interface ValuationData {
  as_of_date: string;
  warehouse_filter: string | null;
  category_filter: string | null;
  items: ValuationItem[];
  total_items: number;
  total_quantity: number;
  total_value: string;
}

interface Warehouse {
  id: string;
  name: string;
}

interface Category {
  id: string;
  name: string;
}

export default function ValuationPage() {
  const t = useTranslations("valuationReport");
  const locale = useLocale();
  const fmt = (v: string) => fmtNumber(v, locale);

  const [warehouseId, setWarehouseId] = useState("");
  const [categoryId, setCategoryId] = useState("");

  const params: Record<string, string> = {};
  if (warehouseId) params.warehouse_id = warehouseId;
  if (categoryId) params.category_id = categoryId;

  const { data: warehouses } = useQuery<Warehouse[]>({
    queryKey: ["warehouses"],
    queryFn: () => api.get("/api/v1/warehouses").then((r) => r.data),
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: () => api.get("/api/v1/inventory/categories").then((r) => r.data),
  });

  const { data, isLoading } = useQuery<ValuationData>({
    queryKey: ["valuation", warehouseId, categoryId],
    queryFn: () =>
      api
        .get("/api/v1/reports/valuation", { params })
        .then((r) => r.data),
  });

  if (isLoading || !data) {
    return <p className="text-muted-foreground">{t("loadingReport")}</p>;
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("asOf")} {data.as_of_date}
      </p>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          value={warehouseId}
          onChange={(e) => setWarehouseId(e.target.value)}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">{t("allWarehouses")}</option>
          {warehouses?.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>

        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">{t("allCategories")}</option>
          {categories?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <ExportButton
          baseUrl="/api/v1/reports/valuation"
          params={params}
          locale={locale}
        />
      </div>

      {/* Summary Cards */}
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalItems")}
          </p>
          <p className="mt-1 text-2xl font-bold">{data.total_items}</p>
        </div>
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalQuantity")}
          </p>
          <p className="mt-1 text-2xl font-bold">{data.total_quantity.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("totalValue")}
          </p>
          <p className="mt-1 text-2xl font-bold">{fmt(data.total_value)} SAR</p>
        </div>
      </div>

      {/* Table */}
      {data.items.length === 0 ? (
        <p className="text-center text-muted-foreground">{t("noItems")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("sku")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("product")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("category")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("quantity")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("costPrice")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("totalValue")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr
                  key={item.product_id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-4 py-2.5 font-mono text-xs">{item.sku}</td>
                  <td className="px-4 py-2.5 font-medium">{item.name}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{item.category}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{item.quantity}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(item.cost_price)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                    {fmt(item.total_value)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-foreground bg-muted/30 font-bold">
                <td className="px-4 py-3" colSpan={3}>
                  {data.total_items} {t("totalItems").toLowerCase()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {data.total_quantity.toLocaleString()}
                </td>
                <td className="px-4 py-3" />
                <td className="px-4 py-3 text-right tabular-nums">
                  {fmt(data.total_value)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
