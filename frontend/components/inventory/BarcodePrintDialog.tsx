"use client";

import { useEffect, useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import JsBarcode from "jsbarcode";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Product {
  id: string;
  name: string;
  sku: string;
  unit_price: string;
}

interface BarcodePrintDialogProps {
  products: Product[];
  onClose: () => void;
}

type LabelSize = "50x30" | "60x40" | "70x40";

export function BarcodePrintDialog({ products, onClose }: BarcodePrintDialogProps) {
  const t = useTranslations("inventory");
  const tc = useTranslations("common");

  const [labelSize, setLabelSize] = useState<LabelSize>("50x30");
  const [quantities, setQuantities] = useState<Record<string, number>>(() =>
    Object.fromEntries(products.map((p) => [p.id, 1])),
  );

  const totalLabels = Object.values(quantities).reduce((sum, qty) => sum + qty, 0);

  const renderBarcodes = useCallback(() => {
    products.forEach((product) => {
      const qty = quantities[product.id] || 1;
      for (let i = 0; i < qty; i++) {
        for (const prefix of ["preview", "print"]) {
          const el = document.getElementById(`barcode-${prefix}-${product.id}-${i}`);
          if (el) {
            try {
              JsBarcode(el, product.sku, {
                format: "CODE128",
                width: 1.5,
                height: 40,
                displayValue: false,
                margin: 0,
              });
            } catch {
              // Invalid SKU for barcode encoding — leave SVG empty
            }
          }
        }
      }
    });
  }, [products, quantities]);

  useEffect(() => {
    // Small delay to ensure SVGs are mounted
    const timer = setTimeout(renderBarcodes, 50);
    return () => clearTimeout(timer);
  }, [renderBarcodes]);

  const handlePrint = () => {
    window.print();
  };

  const handleQuantityChange = (productId: string, value: string) => {
    const qty = Math.max(1, Math.min(100, parseInt(value, 10) || 1));
    setQuantities((prev) => ({ ...prev, [productId]: qty }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 print:hidden">
      <div className="w-full max-w-3xl rounded-lg border bg-card p-6 shadow-lg max-h-[90vh] overflow-y-auto">
        <h2 className="mb-4 text-lg font-semibold">{t("barcodePrintTitle")}</h2>

        {/* Configuration */}
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          {/* Label Size */}
          <div>
            <label className="mb-1 block text-sm font-medium">{t("labelSize")}</label>
            <select
              value={labelSize}
              onChange={(e) => setLabelSize(e.target.value as LabelSize)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="50x30">{t("labelSmall")}</option>
              <option value="60x40">{t("labelMedium")}</option>
              <option value="70x40">{t("labelLarge")}</option>
            </select>
          </div>

          {/* Total Labels Count */}
          <div className="flex items-end">
            <p className="text-sm text-muted-foreground">
              {t("totalLabels")}: <strong className="text-foreground">{totalLabels}</strong>
            </p>
          </div>
        </div>

        {/* Quantity per product */}
        <div className="mb-4 space-y-2">
          {products.map((product) => (
            <div key={product.id} className="flex items-center gap-3 rounded border px-3 py-2">
              <span className="flex-1 text-sm font-medium truncate">{product.name}</span>
              <span className="text-xs text-muted-foreground font-mono">{product.sku}</span>
              <input
                type="number"
                min={1}
                max={100}
                value={quantities[product.id]}
                onChange={(e) => handleQuantityChange(product.id, e.target.value)}
                className="w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-center"
              />
            </div>
          ))}
        </div>

        {/* Preview */}
        <div className="mb-4">
          <h3 className="mb-2 text-sm font-medium">{t("preview")}</h3>
          <div className="max-h-64 overflow-y-auto rounded border bg-gray-50 dark:bg-muted/30 p-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {products.flatMap((product) => {
                const qty = quantities[product.id] || 1;
                return Array.from({ length: qty }, (_, i) => (
                  <div
                    key={`preview-${product.id}-${i}`}
                    className="flex flex-col items-center border border-gray-300 bg-white p-2 text-xs text-black rounded"
                  >
                    <div className="font-semibold truncate w-full text-center text-[10px]">
                      {product.name}
                    </div>
                    <svg id={`barcode-preview-${product.id}-${i}`} className="my-1" />
                    <div className="font-mono text-[9px]">{product.sku}</div>
                    <div className="font-bold text-[10px]">
                      {Number(product.unit_price).toFixed(2)} {tc("sar")}
                    </div>
                  </div>
                ));
              })}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button className="flex-1" onClick={handlePrint}>
            <Printer className="size-4" />
            {t("printButton")}
          </Button>
          <Button variant="outline" onClick={onClose}>
            {tc("cancel")}
          </Button>
        </div>
      </div>

      {/* Print Area — only visible when printing */}
      <div id="barcode-label-sheet" className="hidden print:block">
        <div className="label-grid">
          {products.flatMap((product) => {
            const qty = quantities[product.id] || 1;
            return Array.from({ length: qty }, (_, i) => (
              <div
                key={`print-${product.id}-${i}`}
                className={`barcode-label size-${labelSize}`}
              >
                <div style={{ fontWeight: "bold", textAlign: "center", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", width: "100%" }}>
                  {product.name}
                </div>
                <svg id={`barcode-print-${product.id}-${i}`} />
                <div style={{ fontFamily: "monospace", textAlign: "center" }}>
                  {product.sku}
                </div>
                <div style={{ fontWeight: "bold", textAlign: "center" }}>
                  {Number(product.unit_price).toFixed(2)} SAR
                </div>
              </div>
            ));
          })}
        </div>
      </div>
    </div>
  );
}
