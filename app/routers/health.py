from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.services.s3 import get_s3_client
from app.config import settings
import time
import psutil
import os

router = APIRouter()


@router.get("/")
def health_check(db: Session = Depends(get_db)):
    """Endpoint principal de salud — usado por load balancers y CloudWatch."""
    checks = {}
    overall = "healthy"

    # ── DB check ─────────────────────────────────────────────────────────────
    try:
        start = time.time()
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "ok",
            "latency_ms": round((time.time() - start) * 1000, 2),
        }
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # ── S3 check ──────────────────────────────────────────────────────────────
    if settings.S3_BUCKET_NAME:
        try:
            client = get_s3_client()
            client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
            checks["s3"] = {"status": "ok"}
        except Exception as e:
            checks["s3"] = {"status": "error", "detail": str(e)}
            overall = "degraded"
    else:
        checks["s3"] = {"status": "not_configured"}

    # ── System resources ──────────────────────────────────────────────────────
    checks["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }

    return {
        "status": overall,
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "timestamp": time.time(),
        "checks": checks,
    }


@router.get("/ping")
def ping():
    """Ping ultra-ligero para load balancers."""
    return {"pong": True}
