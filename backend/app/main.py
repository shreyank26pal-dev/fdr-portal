"""SecureDeposit - AICTE Security Deposit / FDR Management Portal (backend).

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401  (register tables)
from app.config import settings
from app.context import request_ip
from app.database import Base, SessionLocal, engine
from app.routers import admin, alerts, auth, bank, dashboard, documents, instruments, me, refunds
from app.services import clock, config_service, monitor, ocr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        config_service.seed_defaults(db)
        clock.set_offset_days(int(config_service.get(db, "clock_offset_days") or 0))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.ENABLE_SCHEDULER:
        monitor.start_scheduler()
    log.info("Simulated today: %s (offset %s days)", clock.today(), clock.offset_days())
    yield
    monitor.stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Backend for the AICTE Security Deposit / FDR portal (SIH26265).\n\n"
        "**Login:** click *Authorize* and use a demo account from the README "
        "(e.g. `officer@aicte-demo.in` / `Password@123`).\n\n"
        "Anything marked **[SIMULATED]** or **[DEMO]** is a sandbox for the prototype and is labelled as such."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Content-SHA256", "X-Integrity"],
)


@app.middleware("http")
async def context_and_security_headers(request: Request, call_next):
    fwd = request.headers.get("x-forwarded-for")
    request_ip.set(fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None))
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.ENV != "dev":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


API = "/api/v1"
for r in (auth.router, me.router, instruments.router, documents.router, refunds.router, alerts.router,
          dashboard.router, bank.router, admin.router, admin.public):
    app.include_router(r, prefix=API)


@app.get("/health", tags=["System"])
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "simulated_today": clock.today(),
        "clock_offset_days": clock.offset_days(),
        "ocr": {"tesseract": ocr.tesseract_available(), "google_vision": bool(settings.GOOGLE_VISION_API_KEY)},
        "email": "smtp" if settings.SMTP_HOST else "simulated",
        "demo_mode": settings.DEMO_MODE,
    }


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "docs": "/docs", "health": "/health"}
