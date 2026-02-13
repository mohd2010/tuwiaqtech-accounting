# backend/app/models/accounting.py — BACKWARD COMPATIBILITY SHIM
#
# The original monolith has been split into domain modules. This file
# re-exports every public name so existing imports continue to work.

from backend.app.models.user import RoleEnum, User
from backend.app.models.account import AccountType, Account
from backend.app.models.journal import JournalEntry, TransactionSplit
from backend.app.models.audit import AuditLog

__all__ = [
    "RoleEnum",
    "User",
    "AccountType",
    "Account",
    "JournalEntry",
    "TransactionSplit",
    "AuditLog",
]
