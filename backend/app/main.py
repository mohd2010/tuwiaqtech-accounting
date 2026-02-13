from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.api import api_router
from backend.app.core.config import settings
from backend.app.middleware.language import LanguageMiddleware
from backend.app.middleware.request_id import RequestIDMiddleware
from backend.app.middleware.security import SecurityHeadersMiddleware

app = FastAPI(title="Tuwaiq Outdoor Accounting & POS")

# ─── CORS — restrict to configured origins (NCA ECC 2-5) ─────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language"],
    expose_headers=["Content-Disposition"],
)

# ─── Custom middleware (outermost executes first) ─────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LanguageMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router)
