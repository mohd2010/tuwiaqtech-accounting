from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    accounts,
    audit,
    auth,
    banking,
    customers,
    einvoice,
    expenses,
    fiscal,
    inventory,
    recurring,
    invoices,
    journal,
    organization,
    pos,
    purchase_orders,
    purchase_returns,
    quotes,
    reports,
    returns,
    sales,
    suppliers,
    users,
    warehouses,
    zatca_onboarding,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(journal.router, prefix="/journal", tags=["journal"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(pos.router, prefix="/pos", tags=["pos"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
api_router.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["purchase-orders"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(returns.router, prefix="/returns", tags=["returns"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(sales.router, prefix="/sales", tags=["sales"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(warehouses.router, prefix="/warehouses", tags=["warehouses"])
api_router.include_router(banking.router, prefix="/banking", tags=["banking"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(fiscal.router, prefix="/fiscal-close", tags=["fiscal-close"])
api_router.include_router(recurring.router, prefix="/recurring-entries", tags=["recurring-entries"])
api_router.include_router(purchase_returns.router, prefix="/purchase-returns", tags=["purchase-returns"])
api_router.include_router(organization.router, prefix="/organization", tags=["organization"])
api_router.include_router(einvoice.router, prefix="/einvoices", tags=["einvoices"])
api_router.include_router(zatca_onboarding.router, prefix="/zatca", tags=["zatca"])
