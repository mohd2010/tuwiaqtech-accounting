"use client";

import { useEffect } from "react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  Package,
  BookOpen,
  ClipboardMinus,
  Landmark,
  ShoppingCart,
  LogOut,
  FileText,
  Scale,
  ClipboardList,
  Truck,
  ClipboardCheck,
  RotateCcw,
  Receipt,
  ScrollText,
  FileCheck,
  Clock,
  Warehouse,
  ArrowLeftRight,
  Building2,
  Users,
  Lock,
  Repeat,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import LanguageSwitcher from "@/components/LanguageSwitcher";

// ─── Types ───────────────────────────────────────────────────────────────────

interface NavItem {
  href: "/dashboard" | "/dashboard/inventory" | "/dashboard/inventory/adjustments" | "/dashboard/inventory/warehouses" | "/dashboard/inventory/transfers" | "/dashboard/journal" | "/dashboard/accounts" | "/dashboard/pos" | "/dashboard/pos/returns" | "/dashboard/pos/shifts" | "/dashboard/expenses" | "/dashboard/sales" | "/dashboard/quotes" | "/dashboard/suppliers" | "/dashboard/purchase-orders" | "/dashboard/purchase-returns" | "/dashboard/reports/income-statement" | "/dashboard/reports/balance-sheet" | "/dashboard/reports/trial-balance" | "/dashboard/reports/general-ledger" | "/dashboard/reports/vat-report" | "/dashboard/reports/cash-flow" | "/dashboard/reports/ar-aging" | "/dashboard/reports/ap-aging" | "/dashboard/reports/valuation" | "/dashboard/banking" | "/dashboard/invoices" | "/dashboard/users" | "/dashboard/fiscal-close" | "/dashboard/recurring" | "/dashboard/settings" | "/dashboard/einvoices" | "/dashboard/setup";
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Permission code(s) required — item hidden if user lacks any */
  permission?: string;
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

function isGroup(item: NavItem | NavGroup): item is NavGroup {
  return "heading" in item;
}

/** Map route prefixes to the permission required to access them */
const ROUTE_PERMISSION_MAP: Record<string, string> = {
  "/dashboard/reports": "report:read",
  "/dashboard/journal": "journal:read",
  "/dashboard/accounts": "account:read",
  "/dashboard/expenses": "expense:read",
  "/dashboard/suppliers": "supplier:read",
  "/dashboard/purchase-orders": "purchase:read",
  "/dashboard/purchase-returns": "purchase:read",
  "/dashboard/quotes": "quote:read",
  "/dashboard/banking": "banking:read",
  "/dashboard/invoices": "invoice:read",
  "/dashboard/users": "user:manage",
  "/dashboard/fiscal-close": "fiscal:close",
  "/dashboard/recurring": "recurring:read",
  "/dashboard/settings": "organization:write",
  "/dashboard/einvoices": "einvoice:read",
  "/dashboard/sales": "sales:read",
  "/dashboard/pos": "pos:sale",
  "/dashboard/inventory": "inventory:read",
};

// ─── Layout ──────────────────────────────────────────────────────────────────

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const t = useTranslations("Sidebar");
  const tc = useTranslations("common");

  const userPerms = user?.permissions ?? [];
  const hasPermission = (code?: string) => !code || userPerms.includes(code);

  // ── Full navigation definition with permission gates ──────────────────
  const ALL_SECTIONS: (NavItem | NavGroup)[] = [
    { href: "/dashboard", label: t("dashboard"), icon: LayoutDashboard },
    {
      heading: t("inventory"),
      items: [
        { href: "/dashboard/inventory", label: t("inventory"), icon: Package, permission: "inventory:read" },
        { href: "/dashboard/inventory/adjustments", label: t("adjustments"), icon: ClipboardMinus, permission: "inventory:adjust" },
        { href: "/dashboard/inventory/warehouses", label: t("warehouses"), icon: Warehouse, permission: "warehouse:read" },
        { href: "/dashboard/inventory/transfers", label: t("transfers"), icon: ArrowLeftRight, permission: "warehouse:write" },
      ],
    },
    {
      heading: t("accounting"),
      items: [
        { href: "/dashboard/journal", label: t("journal"), icon: BookOpen, permission: "journal:read" },
        { href: "/dashboard/accounts", label: t("chartOfAccounts"), icon: Landmark, permission: "account:read" },
        { href: "/dashboard/recurring", label: t("recurringEntries"), icon: Repeat, permission: "recurring:read" },
        { href: "/dashboard/fiscal-close", label: t("fiscalClose"), icon: Lock, permission: "fiscal:close" },
        { href: "/dashboard/settings", label: t("organizationSettings"), icon: Building2, permission: "organization:write" },
      ],
    },
    { href: "/dashboard/expenses", label: t("expenses"), icon: Receipt, permission: "expense:read" },
    {
      heading: t("pos"),
      items: [
        { href: "/dashboard/pos", label: t("pos"), icon: ShoppingCart, permission: "pos:sale" },
        { href: "/dashboard/pos/returns", label: t("returns"), icon: RotateCcw, permission: "returns:process" },
        { href: "/dashboard/pos/shifts", label: t("shifts"), icon: Clock, permission: "pos:shift" },
      ],
    },
    { href: "/dashboard/sales", label: t("salesHistory"), icon: ScrollText, permission: "sales:read" },
    { href: "/dashboard/quotes", label: t("quotes"), icon: FileCheck, permission: "quote:read" },
    {
      heading: t("banking"),
      items: [
        { href: "/dashboard/banking", label: t("bankReconciliation"), icon: Building2, permission: "banking:read" },
      ],
    },
    {
      heading: t("receivables"),
      items: [
        { href: "/dashboard/invoices", label: t("creditInvoices"), icon: FileText, permission: "invoice:read" },
      ],
    },
    {
      heading: t("supplyChain"),
      items: [
        { href: "/dashboard/suppliers", label: t("suppliers"), icon: Truck, permission: "supplier:read" },
        { href: "/dashboard/purchase-orders", label: t("purchaseOrders"), icon: ClipboardCheck, permission: "purchase:read" },
        { href: "/dashboard/purchase-returns", label: t("purchaseReturns"), icon: RotateCcw, permission: "purchase:read" },
      ],
    },
    {
      heading: t("zatca"),
      items: [
        { href: "/dashboard/einvoices", label: t("eInvoices"), icon: FileCheck, permission: "einvoice:read" },
      ],
    },
    {
      heading: t("userManagement"),
      items: [
        { href: "/dashboard/users", label: t("users"), icon: Users, permission: "user:manage" },
      ],
    },
    {
      heading: t("reports"),
      items: [
        { href: "/dashboard/reports/income-statement", label: t("incomeStatement"), icon: FileText, permission: "report:read" },
        { href: "/dashboard/reports/balance-sheet", label: t("balanceSheet"), icon: Scale, permission: "report:read" },
        { href: "/dashboard/reports/trial-balance", label: t("trialBalance"), icon: ClipboardList, permission: "report:read" },
        { href: "/dashboard/reports/general-ledger", label: t("generalLedger"), icon: BookOpen, permission: "report:read" },
        { href: "/dashboard/reports/vat-report", label: t("vatReport"), icon: Receipt, permission: "report:read" },
        { href: "/dashboard/reports/cash-flow", label: t("cashFlow"), icon: ArrowLeftRight, permission: "report:read" },
        { href: "/dashboard/reports/ar-aging", label: t("arAging"), icon: Clock, permission: "report:read" },
        { href: "/dashboard/reports/ap-aging", label: t("apAging"), icon: Clock, permission: "report:read" },
        { href: "/dashboard/reports/valuation", label: t("valuation"), icon: Package, permission: "report:read" },
      ],
    },
  ];

  // Filter sections based on user permissions
  const navSections = ALL_SECTIONS.map((section) => {
    if (isGroup(section)) {
      const filtered = section.items.filter((item) => hasPermission(item.permission));
      if (filtered.length === 0) return null;
      return { ...section, items: filtered };
    }
    return hasPermission(section.permission) ? section : null;
  }).filter(Boolean) as (NavItem | NavGroup)[];

  // ── Route guard: redirect if user lacks permission for current route ────
  useEffect(() => {
    for (const [prefix, perm] of Object.entries(ROUTE_PERMISSION_MAP)) {
      if (pathname.startsWith(prefix) && !userPerms.includes(perm)) {
        router.replace("/dashboard");
        return;
      }
    }
  }, [userPerms, pathname, router]);

  // ── Onboarding guard: redirect to setup wizard if org not configured ────
  useEffect(() => {
    if (!user) return;
    if (!user.orgConfigured && pathname !== "/dashboard/setup") {
      router.replace("/dashboard/setup");
    }
  }, [user, pathname, router]);

  const renderLink = (item: NavItem) => {
    const isActive =
      item.href === "/dashboard" || item.href === "/dashboard/inventory" || item.href === "/dashboard/pos"
        ? pathname === item.href
        : pathname.startsWith(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground",
        )}
      >
        <item.icon className="size-4" />
        {item.label}
      </Link>
    );
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col ltr:border-r rtl:border-l border-sidebar-border bg-sidebar text-sidebar-foreground">
        <div className="border-b border-sidebar-border px-4 py-4">
          <h2 className="text-lg font-bold">{tc("appName")}</h2>
          <p className="text-xs text-muted-foreground">
            {user?.username}{" "}
            <span
              className={cn(
                "ltr:ml-1 rtl:mr-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                user?.role === "CASHIER"
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                  : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
              )}
            >
              {user?.role}
            </span>
          </p>
        </div>

        <nav className="flex-1 space-y-1 overflow-auto px-2 py-3">
          {navSections.map((section) => {
            if (isGroup(section)) {
              return (
                <div key={section.heading} className="mt-4">
                  <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {section.heading}
                  </p>
                  <div className="space-y-0.5">
                    {section.items.map(renderLink)}
                  </div>
                </div>
              );
            }
            return renderLink(section);
          })}
        </nav>

        <div className="border-t border-sidebar-border px-2 py-3 space-y-1">
          <LanguageSwitcher />
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors"
          >
            <LogOut className="size-4" />
            {tc("logout")}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-background p-6">
        {children}
      </main>
    </div>
  );
}
