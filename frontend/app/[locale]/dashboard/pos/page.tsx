"use client";

import { useCallback, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  ShoppingCart,
  Minus,
  Plus,
  Trash2,
  CheckCircle,
  ScanBarcode,
  Search,
} from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import InvoiceModal, { type InvoiceData } from "@/components/pos/InvoiceModal";
import { useBarcodeScanner } from "@/hooks/useBarcodeScanner";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Product {
  id: string;
  name: string;
  sku: string;
  unit_price: string;
  current_stock: number;
}

interface CartItem {
  product: Product;
  quantity: number;
}

// ─── Beep helper ─────────────────────────────────────────────────────────────

function playBeep() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 1200;
    gain.gain.value = 0.15;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.1);
  } catch {
    // AudioContext not available — silently ignore
  }
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PosPage() {
  const queryClient = useQueryClient();
  const t = useTranslations("pos");
  const locale = useLocale();
  const [cart, setCart] = useState<Map<string, CartItem>>(new Map());
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);
  const [activeInvoice, setLastInvoice] = useState<InvoiceData | null>(null);
  const [manualBarcode, setManualBarcode] = useState("");
  const manualInputRef = useRef<HTMLInputElement>(null);

  // Payment method state
  const [paymentMethod, setPaymentMethod] = useState<"CASH" | "CARD" | "BANK_TRANSFER">("CASH");
  const [isSplitPayment, setIsSplitPayment] = useState(false);
  const [splitCashAmount, setSplitCashAmount] = useState("");

  // Discount state
  const [discountType, setDiscountType] = useState<"PERCENTAGE" | "FIXED_AMOUNT" | null>(null);
  const [discountValue, setDiscountValue] = useState("");

  const { data: products = [], isLoading } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: () => api.get("/api/v1/inventory/products").then((r) => r.data),
  });

  const showToast = useCallback(
    (message: string, type: "success" | "error") => {
      setToast({ message, type });
      setTimeout(() => setToast(null), 3000);
    },
    [],
  );

  const addToCart = useCallback((product: Product) => {
    setCart((prev) => {
      const next = new Map(prev);
      const existing = next.get(product.id);
      const currentQty = existing?.quantity ?? 0;
      if (currentQty >= product.current_stock) return prev;
      next.set(product.id, { product, quantity: currentQty + 1 });
      return next;
    });
  }, []);

  // ─── Barcode scan handler ───────────────────────────────────────────────

  const handleBarcodeScan = useCallback(
    async (barcode: string) => {
      try {
        const res = await api.post("/api/v1/pos/scan", { barcode });
        const product = res.data as Product;
        addToCart(product);
        playBeep();
        showToast(t("scanAdded", { name: product.name }), "success");
      } catch (err: unknown) {
        const status =
          err && typeof err === "object" && "response" in err
            ? (err as { response?: { status?: number } }).response?.status
            : undefined;
        if (status === 404) {
          showToast(t("scanNotFound", { barcode }), "error");
        } else {
          showToast(t("scanError"), "error");
        }
      }
    },
    [addToCart, showToast, t],
  );

  useBarcodeScanner(handleBarcodeScan);

  const handleManualSubmit = () => {
    const val = manualBarcode.trim();
    if (val.length > 0) {
      handleBarcodeScan(val);
      setManualBarcode("");
    }
  };

  // ─── Cart helpers ───────────────────────────────────────────────────────

  const updateQuantity = useCallback((productId: string, delta: number) => {
    setCart((prev) => {
      const next = new Map(prev);
      const item = next.get(productId);
      if (!item) return prev;
      const newQty = item.quantity + delta;
      if (newQty <= 0) {
        next.delete(productId);
      } else if (newQty <= item.product.current_stock) {
        next.set(productId, { ...item, quantity: newQty });
      }
      return next;
    });
  }, []);

  const removeFromCart = useCallback((productId: string) => {
    setCart((prev) => {
      const next = new Map(prev);
      next.delete(productId);
      return next;
    });
  }, []);

  const cartItems = Array.from(cart.values());
  const cartTotal = cartItems.reduce(
    (sum, item) => sum + Number(item.product.unit_price) * item.quantity,
    0,
  );

  const discountAmount =
    discountType && discountValue && parseFloat(discountValue) > 0
      ? discountType === "PERCENTAGE"
        ? (cartTotal * parseFloat(discountValue)) / 100
        : parseFloat(discountValue)
      : 0;
  const finalTotal = Math.max(cartTotal - discountAmount, 0);

  const saleMutation = useMutation({
    mutationFn: async (items: CartItem[]) => {
      // Build payments array (use finalTotal for amounts)
      let payments: { method: string; amount: string }[] | undefined;
      if (isSplitPayment && splitCashAmount) {
        const cashAmt = parseFloat(splitCashAmount);
        const cardAmt = finalTotal - cashAmt;
        if (cashAmt > 0 && cardAmt > 0) {
          payments = [
            { method: "CASH", amount: cashAmt.toFixed(4) },
            { method: "CARD", amount: cardAmt.toFixed(4) },
          ];
        }
      } else if (paymentMethod !== "CASH") {
        payments = [{ method: paymentMethod, amount: finalTotal.toFixed(4) }];
      }

      const res = await api.post("/api/v1/pos/sale", {
        items: items.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
        })),
        ...(payments ? { payments } : {}),
        ...(discountType && discountValue
          ? { discount_type: discountType, discount_value: discountValue }
          : {}),
      });
      return res.data as InvoiceData;
    },
    onSuccess: (invoice) => {
      setCart(new Map());
      setPaymentMethod("CASH");
      setIsSplitPayment(false);
      setSplitCashAmount("");
      setDiscountType(null);
      setDiscountValue("");
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setLastInvoice(invoice);
      showToast(t("saleSuccess"), "success");
    },
    onError: () => {
      showToast(t("saleFailed"), "error");
    },
  });

  return (
    <div className="flex h-full gap-6">
      {/* Product Grid */}
      <div className="flex-1">
        {/* Header row: title + scanner status + manual barcode */}
        <div className="mb-6 flex flex-wrap items-center gap-4">
          <h1 className="text-3xl font-bold">{t("title")}</h1>

          {/* Scanner status indicator */}
          <div className="flex items-center gap-1.5 rounded-full border border-green-500/30 bg-green-50 px-3 py-1 text-xs font-medium text-green-700 dark:bg-green-950/30 dark:text-green-400">
            <ScanBarcode className="size-3.5" />
            <span>{t("scannerActive")}</span>
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-green-500" />
            </span>
          </div>

          {/* Manual barcode input */}
          <div className="ltr:ml-auto rtl:mr-auto flex items-center gap-1">
            <input
              ref={manualInputRef}
              type="text"
              value={manualBarcode}
              onChange={(e) => setManualBarcode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleManualSubmit();
                }
              }}
              placeholder={t("manualBarcode")}
              className="h-9 w-48 rounded-md border bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={handleManualSubmit}
              disabled={manualBarcode.trim().length === 0}
            >
              <Search className="size-4 ltr:mr-1 rtl:ml-1" />
              {t("search")}
            </Button>
          </div>
        </div>

        {isLoading ? (
          <p className="text-muted-foreground">{t("loadingProducts")}</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
            {products.map((p) => {
              const inCart = cart.get(p.id)?.quantity ?? 0;
              const outOfStock = p.current_stock === 0;
              return (
                <button
                  key={p.id}
                  disabled={outOfStock}
                  onClick={() => addToCart(p)}
                  className={cn(
                    "flex flex-col rounded-lg border p-4 text-left transition-colors",
                    outOfStock
                      ? "cursor-not-allowed border-border bg-muted/30 opacity-50"
                      : "border-border bg-card hover:border-primary/40 hover:shadow-sm",
                    inCart > 0 && "border-primary/60 ring-1 ring-primary/20",
                  )}
                >
                  <span className="text-sm font-semibold">{p.name}</span>
                  <span className="mt-1 text-lg font-bold">
                    {Number(p.unit_price).toFixed(2)} SAR
                  </span>
                  <span
                    className={cn(
                      "mt-2 text-xs",
                      p.current_stock <= 5
                        ? "text-red-500"
                        : "text-muted-foreground",
                    )}
                  >
                    {outOfStock
                      ? t("outOfStock")
                      : t("inStock", { count: p.current_stock })}
                  </span>
                  {inCart > 0 && (
                    <span className="mt-1 text-xs font-medium text-primary">
                      {t("inCart", { count: inCart })}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Checkout Sidebar */}
      <div className="flex w-80 flex-col rounded-lg border bg-card">
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <ShoppingCart className="size-5" />
          <h2 className="text-lg font-semibold">{t("checkout")}</h2>
          {cartItems.length > 0 && (
            <span className="ltr:ml-auto rtl:mr-auto rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
              {cartItems.length}
            </span>
          )}
        </div>

        <div className="flex-1 overflow-auto px-4 py-3">
          {cartItems.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("tapToAdd")}
            </p>
          ) : (
            <ul className="space-y-3">
              {cartItems.map((item) => (
                <li
                  key={item.product.id}
                  className="flex items-center gap-2 rounded-md border px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {item.product.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {Number(item.product.unit_price).toFixed(2)} x{" "}
                      {item.quantity}
                      {" = "}
                      <span className="font-semibold text-foreground">
                        {(
                          Number(item.product.unit_price) * item.quantity
                        ).toFixed(2)}
                      </span>
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      size="icon-xs"
                      variant="outline"
                      onClick={() => updateQuantity(item.product.id, -1)}
                    >
                      <Minus className="size-3" />
                    </Button>
                    <span className="w-6 text-center text-sm font-medium">
                      {item.quantity}
                    </span>
                    <Button
                      size="icon-xs"
                      variant="outline"
                      onClick={() => updateQuantity(item.product.id, 1)}
                      disabled={item.quantity >= item.product.current_stock}
                    >
                      <Plus className="size-3" />
                    </Button>
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      onClick={() => removeFromCart(item.product.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t px-4 py-3">
          {cartItems.length > 0 &&
            (() => {
              const vatAmount = (finalTotal * 15) / 115;
              const netPrice = finalTotal - vatAmount;
              return (
                <div className="mb-3 space-y-1 text-sm">
                  <div className="flex justify-between text-muted-foreground">
                    <span>{t("subtotalExclVat")}</span>
                    <span>{netPrice.toFixed(2)} SAR</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>{t("vat15")}</span>
                    <span>{vatAmount.toFixed(2)} SAR</span>
                  </div>
                  {discountAmount > 0 && (
                    <>
                      <div className="flex justify-between text-muted-foreground">
                        <span>{t("originalTotal")}</span>
                        <span>{cartTotal.toFixed(2)} SAR</span>
                      </div>
                      <div className="flex justify-between text-green-600 font-medium">
                        <span>{t("discountLabel")}</span>
                        <span>-{discountAmount.toFixed(2)} SAR</span>
                      </div>
                    </>
                  )}
                  <div className="flex justify-between border-t pt-1 text-lg font-bold">
                    <span>{t("total")}</span>
                    <span>{finalTotal.toFixed(2)} SAR</span>
                  </div>
                </div>
              );
            })()}
          {cartItems.length === 0 && (
            <div className="mb-3 flex items-center justify-between text-lg font-bold">
              <span>{t("total")}</span>
              <span>0.00 SAR</span>
            </div>
          )}

          {/* Discount Selector */}
          {cartItems.length > 0 && (
            <div className="mb-3 space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase">{t("discount")}</p>
              <div className="flex gap-1">
                {([null, "PERCENTAGE", "FIXED_AMOUNT"] as const).map((dt) => (
                  <button
                    key={dt ?? "NONE"}
                    onClick={() => {
                      setDiscountType(dt);
                      if (!dt) setDiscountValue("");
                    }}
                    className={cn(
                      "flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
                      discountType === dt
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background hover:bg-muted",
                    )}
                  >
                    {dt === null
                      ? t("noDiscount")
                      : dt === "PERCENTAGE"
                        ? t("percentageDiscount")
                        : t("fixedDiscount")}
                  </button>
                ))}
              </div>
              {discountType && (
                <div className="flex items-center gap-2 text-xs">
                  <label className="w-20 text-muted-foreground">{t("discountValue")}</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max={discountType === "PERCENTAGE" ? 99.99 : cartTotal}
                    value={discountValue}
                    onChange={(e) => setDiscountValue(e.target.value)}
                    className="h-7 flex-1 rounded border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              )}
            </div>
          )}

          {/* Payment Method Selector */}
          {cartItems.length > 0 && (
            <div className="mb-3 space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase">{t("paymentMethod")}</p>
              <div className="flex gap-1">
                {(["CASH", "CARD", "BANK_TRANSFER"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => {
                      setPaymentMethod(m);
                      setIsSplitPayment(false);
                      setSplitCashAmount("");
                    }}
                    className={cn(
                      "flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
                      paymentMethod === m && !isSplitPayment
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background hover:bg-muted",
                    )}
                  >
                    {t(`method_${m}`)}
                  </button>
                ))}
              </div>
              <button
                onClick={() => {
                  setIsSplitPayment(!isSplitPayment);
                  if (!isSplitPayment) setSplitCashAmount("");
                }}
                className={cn(
                  "w-full text-xs text-center py-1 rounded border transition-colors",
                  isSplitPayment
                    ? "border-primary bg-primary/10 text-primary font-semibold"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {isSplitPayment ? t("singlePayment") : t("splitPayment")}
              </button>
              {isSplitPayment && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-xs">
                    <label className="w-20 text-muted-foreground">{t("cashAmount")}</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max={finalTotal}
                      value={splitCashAmount}
                      onChange={(e) => setSplitCashAmount(e.target.value)}
                      className="h-7 flex-1 rounded border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  {splitCashAmount && (
                    <p className="text-xs text-muted-foreground">
                      {t("cardAmount")}: {(finalTotal - parseFloat(splitCashAmount || "0")).toFixed(2)} SAR
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          <Button
            className="w-full"
            size="lg"
            disabled={cartItems.length === 0 || saleMutation.isPending}
            onClick={() => saleMutation.mutate(cartItems)}
          >
            {saleMutation.isPending ? t("processing") : t("completeSale")}
          </Button>
        </div>
      </div>

      {/* Invoice modal */}
      {activeInvoice && (
        <InvoiceModal
          invoice={activeInvoice}
          onClose={() => setLastInvoice(null)}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 ltr:right-6 rtl:left-6 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg",
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white",
          )}
        >
          {toast.type === "success" && <CheckCircle className="size-4" />}
          {toast.message}
        </div>
      )}
    </div>
  );
}
