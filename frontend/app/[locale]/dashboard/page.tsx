"use client";

import { Link } from "@/i18n/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useLocale } from "next-intl";
import {
  DollarSign,
  TrendingUp,
  Package,
  AlertTriangle,
  RefreshCw,
  ShoppingCart,
  ClipboardList,
  Percent,
  CreditCard,
  Landmark,
  Wallet,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fmtNumber } from "@/lib/format";

// ─── Types ───────────────────────────────────────────────────────────────────

interface LowStockItem {
  id: string;
  name: string;
  sku: string;
  current_stock: number;
  reorder_level: number;
}

interface RecentEntry {
  id: string;
  date: string;
  description: string;
  reference: string;
}

interface DashboardData {
  revenue: string;
  net_profit: string;
  inventory_value: string;
  low_stock_count: number;
  low_stock_items: LowStockItem[];
  sales_trend: { date: string; total_sales: string }[];
  recent_activity: RecentEntry[];
  gross_margin_pct: string;
  accounts_receivable: string;
  accounts_payable: string;
  cash_position: string;
  revenue_expense_trend: { date: string; revenue: string; expenses: string }[];
  top_products: { name: string; total: string }[];
  sales_by_payment_method: { method: string; total: string }[];
  cash_flow_forecast: string;
  inventory_turnover: string;
  ar_aging_summary: Record<string, string>;
}

const PAYMENT_COLORS: Record<string, string> = {
  CASH: "hsl(142, 71%, 45%)",
  CARD: "hsl(221, 83%, 53%)",
  BANK_TRANSFER: "hsl(280, 65%, 60%)",
};

const AGING_COLORS: Record<string, string> = {
  current: "hsl(142, 71%, 45%)",
  days_31_60: "hsl(48, 96%, 53%)",
  days_61_90: "hsl(25, 95%, 53%)",
  over_90: "hsl(0, 84%, 60%)",
};

// ─── Page ────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const t = useTranslations("dashboard");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-muted-foreground">
          {t("welcomeBack", { username: user?.username ?? "" })}
        </p>
      </div>

      {/* Role-based view */}
      {user?.role === "CASHIER" ? <CashierView /> : <AnalyticsView />}
    </div>
  );
}

// ─── CashierView — Task Pad (no financial data) ─────────────────────────────

function CashierView() {
  const t = useTranslations("dashboard");

  const tasks = [
    {
      href: "/dashboard/pos" as const,
      label: t("openPOS"),
      description: t("openPOSDesc"),
      icon: ShoppingCart,
      color: "bg-blue-500",
    },
    {
      href: "/dashboard/inventory" as const,
      label: t("checkInventory"),
      description: t("checkInventoryDesc"),
      icon: Package,
      color: "bg-emerald-500",
    },
    {
      href: "/dashboard" as const,
      label: t("myShift"),
      description: t("myShiftDesc"),
      icon: ClipboardList,
      color: "bg-purple-500",
    },
  ];

  return (
    <>
      <p className="text-muted-foreground">{t("cashierWelcome")}</p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tasks.map((task) => (
          <Link key={task.href + task.label} href={task.href}>
            <Card className="group cursor-pointer transition-shadow hover:shadow-lg">
              <CardContent className="flex items-center gap-4 py-6">
                <div
                  className={`flex size-12 shrink-0 items-center justify-center rounded-lg ${task.color} text-white`}
                >
                  <task.icon className="size-6" />
                </div>
                <div>
                  <p className="font-semibold group-hover:underline">
                    {task.label}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {task.description}
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

// ─── AnalyticsView — KPIs, Charts, Profit (Admin/Accountant) ────────────────

function AnalyticsView() {
  const t = useTranslations("dashboard");
  const tc = useTranslations("common");
  const tj = useTranslations("journalPage");
  const locale = useLocale();

  const fmt = (v: string | number) => fmtNumber(v, locale);

  const { data, isLoading, isError, refetch } = useQuery<DashboardData>({
    queryKey: ["dashboard-summary"],
    queryFn: () =>
      api.get("/api/v1/reports/dashboard-summary").then((r) => r.data),
  });

  const trendData = (data?.sales_trend ?? []).map((d) => ({
    date: d.date.slice(5),
    total_sales: Number(d.total_sales),
  }));

  const revExpData = (data?.revenue_expense_trend ?? []).map((d) => ({
    date: d.date.slice(5),
    revenue: Number(d.revenue),
    expenses: Number(d.expenses),
  }));

  const topProductsData = (data?.top_products ?? []).map((p) => ({
    name: p.name,
    total: Number(p.total),
  }));

  const paymentMethodData = (data?.sales_by_payment_method ?? []).map((p) => ({
    name: t(`method_${p.method}` as "method_CASH" | "method_CARD" | "method_BANK_TRANSFER"),
    value: Number(p.total),
    method: p.method,
  }));

  if (isLoading) {
    return (
      <div className="py-20 text-center text-muted-foreground">
        {t("loadingDashboard")}
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30">
        <CardContent className="flex flex-col items-center gap-3 py-10">
          <AlertTriangle className="size-8 text-red-500" />
          <p className="font-medium text-red-600 dark:text-red-400">
            {t("failedToLoad")}
          </p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="size-3" />
            {tc("retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  // AR Aging data
  const agingEntries = Object.entries(data.ar_aging_summary ?? {});
  const agingTotal = agingEntries.reduce((s, [, v]) => s + Number(v), 0);

  return (
    <>
      {/* ── KPI Row 1 ─────────────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard
          title={t("monthlyRevenue")}
          value={`${fmt(data.revenue)} SAR`}
          icon={<DollarSign className="size-4 text-muted-foreground" />}
          subtitle={t("last30Days")}
        />
        <KPICard
          title={t("netProfit")}
          value={`${fmt(data.net_profit)} SAR`}
          icon={<TrendingUp className="size-4 text-muted-foreground" />}
          subtitle={t("revMinusCogs")}
        />
        <KPICard
          title={t("inventoryValue")}
          value={`${fmt(data.inventory_value)} SAR`}
          icon={<Package className="size-4 text-muted-foreground" />}
          subtitle={t("atCost")}
        />
        <KPICard
          title={t("lowStockAlerts")}
          value={String(data.low_stock_count)}
          icon={<AlertTriangle className="size-4 text-muted-foreground" />}
          subtitle={t("atOrBelowReorder")}
          alert={data.low_stock_count > 0}
        />
      </div>

      {/* ── KPI Row 2 (New) ───────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard
          title={t("grossMargin")}
          value={`${fmt(data.gross_margin_pct)}%`}
          icon={<Percent className="size-4 text-muted-foreground" />}
          subtitle={t("revMinusCogsPct")}
        />
        <KPICard
          title={t("accountsReceivable")}
          value={`${fmt(data.accounts_receivable)} SAR`}
          icon={<CreditCard className="size-4 text-muted-foreground" />}
          subtitle={t("outstandingInvoices")}
        />
        <KPICard
          title={t("accountsPayable")}
          value={`${fmt(data.accounts_payable)} SAR`}
          icon={<Landmark className="size-4 text-muted-foreground" />}
          subtitle={t("outstandingSupplier")}
        />
        <KPICard
          title={t("cashPosition")}
          value={`${fmt(data.cash_position)} SAR`}
          icon={<Wallet className="size-4 text-muted-foreground" />}
          subtitle={t("cashPlusBankBalance")}
        />
      </div>

      {/* ── Area Chart — 7-Day Sales Trend ────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("salesTrend")}</CardTitle>
        </CardHeader>
        <CardContent>
          {trendData.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              {t("noSalesData")}
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient
                    id="salesGradient"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor="hsl(221, 83%, 53%)"
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor="hsl(221, 83%, 53%)"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  className="stroke-muted"
                />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis fontSize={12} tickFormatter={(v) => fmt(v)} />
                <Tooltip
                  formatter={(v) => [`${fmt(Number(v))} SAR`, t("sales")]}
                />
                <Area
                  type="monotone"
                  dataKey="total_sales"
                  stroke="hsl(221, 83%, 53%)"
                  strokeWidth={2}
                  fill="url(#salesGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* ── Revenue vs Expenses Bar Chart ─────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("revenueVsExpenses")}</CardTitle>
        </CardHeader>
        <CardContent>
          {revExpData.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              {t("noFinancialData")}
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={revExpData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  className="stroke-muted"
                />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis fontSize={12} tickFormatter={(v) => fmt(v)} />
                <Tooltip
                  formatter={(v: number, name: string) => [
                    `${fmt(v)} SAR`,
                    name === "revenue" ? t("revenue") : t("expenses"),
                  ]}
                />
                <Legend
                  formatter={(value: string) =>
                    value === "revenue" ? t("revenue") : t("expenses")
                  }
                />
                <Bar dataKey="revenue" fill="hsl(142, 71%, 45%)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expenses" fill="hsl(0, 84%, 60%)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* ── Two-column: Top Products | Payment Method Pie ── */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Top 5 Products */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("topProducts")}</CardTitle>
          </CardHeader>
          <CardContent>
            {topProductsData.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                {t("noFinancialData")}
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={topProductsData} layout="vertical">
                  <CartesianGrid
                    strokeDasharray="3 3"
                    className="stroke-muted"
                  />
                  <XAxis type="number" fontSize={12} tickFormatter={(v) => fmt(v)} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    fontSize={12}
                    width={120}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(v: number) => [`${fmt(v)} SAR`]}
                  />
                  <Bar dataKey="total" fill="hsl(221, 83%, 53%)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Sales by Payment Method */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t("salesByPaymentMethod")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {paymentMethodData.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                {t("noFinancialData")}
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={paymentMethodData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, percent }) =>
                      `${name} ${(percent * 100).toFixed(0)}%`
                    }
                  >
                    {paymentMethodData.map((entry) => (
                      <Cell
                        key={entry.method}
                        fill={PAYMENT_COLORS[entry.method] ?? "hsl(220, 14%, 46%)"}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => [`${fmt(v)} SAR`]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Mini KPI Row: Cash Flow Forecast | Inventory Turnover ── */}
      <div className="grid gap-4 sm:grid-cols-2">
        <KPICard
          title={t("cashFlowForecast")}
          value={`${fmt(data.cash_flow_forecast)} SAR`}
          icon={<Wallet className="size-4 text-muted-foreground" />}
          subtitle={t("cashFlowForecastDesc")}
        />
        <KPICard
          title={t("inventoryTurnover")}
          value={`${fmt(data.inventory_turnover)}x`}
          icon={<Package className="size-4 text-muted-foreground" />}
          subtitle={t("inventoryTurnoverDesc")}
        />
      </div>

      {/* ── Bottom Row: Low Stock + Recent Entries + AR Aging ── */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Low Stock Items */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("lowStockItems")}</CardTitle>
          </CardHeader>
          <CardContent>
            {data.low_stock_items.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t("allWellStocked")}
              </p>
            ) : (
              <div className="space-y-3">
                {data.low_stock_items.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border px-4 py-3"
                  >
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="text-xs text-muted-foreground">
                        SKU: {item.sku} &middot; {t("stock")}:{" "}
                        <span className="font-semibold text-red-500">
                          {item.current_stock}
                        </span>{" "}
                        / {item.reorder_level} {t("min")}
                      </p>
                    </div>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/dashboard/purchase-orders">
                        {t("restock")}
                      </Link>
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Journal Entries */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t("recentJournalEntries")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.recent_activity.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {tj("noEntries")}
              </p>
            ) : (
              <div className="space-y-3">
                {data.recent_activity.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-lg border px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium leading-snug">
                        {entry.description}
                      </p>
                      <span className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">
                        {new Date(entry.date).toLocaleDateString(
                          locale === "ar" ? "ar-SA-u-nu-latn" : "en-US",
                          { month: "short", day: "numeric" },
                        )}
                      </span>
                    </div>
                    {entry.reference && (
                      <p className="mt-1 font-mono text-xs text-muted-foreground">
                        {entry.reference}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* AR Aging Summary */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("arAgingSummary")}</CardTitle>
          </CardHeader>
          <CardContent>
            {agingTotal === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t("noOutstandingAR")}
              </p>
            ) : (
              <div className="space-y-4">
                {(
                  [
                    ["current", t("agingCurrent")],
                    ["days_31_60", t("aging31_60")],
                    ["days_61_90", t("aging61_90")],
                    ["over_90", t("agingOver90")],
                  ] as const
                ).map(([key, label]) => {
                  const val = Number(data.ar_aging_summary[key] ?? "0");
                  const pct = agingTotal > 0 ? (val / agingTotal) * 100 : 0;
                  return (
                    <div key={key}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span>{label}</span>
                        <span className="font-medium tabular-nums">
                          {fmt(val)} SAR
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full transition-all"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: AGING_COLORS[key],
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

// ─── KPI Card Component ──────────────────────────────────────────────────────

function KPICard({
  title,
  value,
  icon,
  subtitle,
  alert,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  subtitle: string;
  alert?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div
          className={`text-2xl font-bold tabular-nums ${
            alert ? "text-red-500" : ""
          }`}
        >
          {value}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
      </CardContent>
    </Card>
  );
}
