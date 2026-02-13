# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: Tuwaiq Outdoor Accounting & POS

A double-entry accounting system with ACID compliance, role-based access (Admin, Accountant, Cashier), POS with multi-payment support, inventory/warehouse management, and bank reconciliation. Saudi Arabia market — ZATCA-compliant invoices, 15% VAT.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (Mapped types), Pydantic v2, python-jose (JWT)
- **Database:** PostgreSQL 16+ with `Numeric(20,4)` for all monetary columns
- **Frontend:** Next.js 14 (App Router), TypeScript strict, TailwindCSS, shadcn/ui, TanStack Query, next-intl (en/ar)
- **Testing:** pytest with SAVEPOINT/ROLLBACK isolation (no test DB cleanup needed)

## Common Commands

```bash
uvicorn backend.app.main:app --reload          # Run backend server
alembic upgrade head                            # Apply migrations
alembic revision --autogenerate -m "desc"       # Generate migration
pytest backend/tests                            # Run all tests
pytest backend/tests/test_pos.py -v             # Run one test file
pytest backend/tests/test_pos.py::TestPOS::test_sale -v  # Single test
```

## Architecture

### Backend Layers

```
API endpoints (backend/app/api/v1/endpoints/)
    ↓ thin controllers, no business logic
Service layer (backend/app/services/)
    ↓ all business logic, DB writes, audit logging
ORM models (backend/app/models/)     Schemas (backend/app/schemas/)
    ↓                                    ↓
PostgreSQL                          Pydantic validation (separate from ORM)
```

- **Endpoints** receive Pydantic schemas, call service functions, return Pydantic schemas
- **Services** accept `db: Session` + primitives, perform all DB operations, call `log_action()` for audit
- **Models** use SQLAlchemy 2.0 `Mapped[]` type annotations with `mapped_column()`

### Key Backend Modules

| Module | Models | Service | Endpoints |
|--------|--------|---------|-----------|
| Accounting | `accounting.py` (User, Account, JournalEntry, TransactionSplit, AuditLog) | `journal.py`, `accounts.py` | `journal.py`, `accounts.py`, `auth.py` |
| Inventory | `inventory.py` (Product, Category, Warehouse, WarehouseStock) | `inventory.py`, `warehouse.py` | `inventory.py`, `warehouses.py` |
| POS | `pos.py` (Register, Shift, PaymentMethod, SalePayment) | `pos.py` | `pos.py` |
| Banking | `banking.py` (BankStatementLine, ReconciliationStatus) | `bank_reconciliation.py` | `banking.py` |
| Suppliers | `supplier.py` | `supplier_payment.py` | `suppliers.py`, `purchase_orders.py` |
| Customers | `customer.py` | — | `customers.py` |
| Returns | `returns.py` | `returns.py` | `returns.py` |
| Quotes | `quotes.py` | `quotes.py` | `quotes.py` |

### Authentication & Authorization

- JWT Bearer tokens (HS256) via `backend/app/core/security.py`
- Three roles: `ADMIN`, `ACCOUNTANT`, `CASHIER` (enum in `accounting.py`)
- Dependencies in `backend/app/api/deps.py`: `get_current_user`, `get_current_active_admin`
- Role checks in endpoints: compare `current_user.role` against allowed roles
- Frontend stores token in localStorage + cookie; middleware redirects unauthenticated users

### Chart of Accounts (hardcoded codes used by services)

- `1000` — Cash (POS cash payments)
- `1100` — Inventory (COGS tracking)
- `1200` — Bank (card/bank transfer payments, bank reconciliation)
- `2200` — VAT Payable (15% VAT)
- `4000` — Sales Revenue
- `5000` — COGS

### POS Sale Flow (`services/pos.py → process_sale()`)

1. Validate items, compute line totals with VAT (15%)
2. Check warehouse stock (resolved from active shift's register)
3. Create JournalEntry with balanced splits: DEBIT asset accounts (Cash/Bank per payment method), CREDIT Sales + VAT Payable + COGS
4. Create SalePayment records per payment method
5. Decrement stock, log audit, return invoice data with ZATCA QR

### Test Infrastructure

- `conftest.py` uses SAVEPOINT pattern: each test runs inside a nested transaction that rolls back
- `db` fixture yields a Session; `client` fixture overrides `get_db` dependency
- `seed_accounts` fixture creates required Chart of Accounts entries
- API tests use `auth(token)` helper for Authorization headers
- API tests using POS sale endpoint need `stock_at_main` fixture for warehouse stock

### Frontend Structure

```
frontend/
├── app/[locale]/dashboard/    # Dashboard pages (pos, banking, accounting, etc.)
├── app/[locale]/login/        # Login page
├── components/                # Reusable components (pos/, ui/)
├── context/AuthContext.tsx     # Auth state (JWT token, user, role)
├── lib/api.ts                 # Axios instance (base URL, token interceptor)
├── messages/en.json, ar.json  # i18n translations
├── i18n/routing.ts            # Locale config (en default, ar)
└── middleware.ts               # Auth guard + intl middleware
```

- RTL support: Arabic locale uses `dir="rtl"`
- All API calls go through `lib/api.ts` Axios instance
- Dashboard sidebar in `layout.tsx` restricts routes by role (`RESTRICTED_PREFIXES`)

## Critical Rules

1. **Financial precision:** NEVER use `float` for money. Use `decimal.Decimal` in Python and `Numeric(precision=20, scale=4)` in SQL.
2. **Double-entry enforcement:** Every journal entry must satisfy `sum(debits) == sum(credits)`.
3. **Journal entry immutability:** Journal entries are never updated or deleted. Corrections are made by posting reversal entries.
4. **Audit logging:** All state changes (prices, inventory, permissions, sales) must be logged via `services/audit.py → log_action()`.
5. **Type safety:** Python code must pass mypy strict mode. Frontend uses strict TypeScript — no `any`.
6. **Migrations:** Chain via `down_revision`. PostgreSQL ENUMs must use `create_type=False` when explicitly calling `.create(checkfirst=True)` before `create_table`.

## Frontend Guidelines

1. Use `"use client"` only when necessary (hooks, interactivity). Default to Server Components.
2. Use `TanStack Query` (`useMutation`/`useQuery`) for all server state.
3. Use `react-hook-form` with `zod` schema validation for forms.
4. Use Tailwind CSS utility classes only. No CSS files.
5. All API calls must go through `lib/api.ts`, never `fetch` directly.
6. i18n: add keys to both `messages/en.json` and `messages/ar.json`. Access via `useTranslations("Section")`.
