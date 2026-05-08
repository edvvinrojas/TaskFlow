from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import logging
import time
from contextlib import asynccontextmanager

from app.database import engine, Base
from app.routers import tasks, users, files, health
from app.config import settings

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("taskflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TaskFlow")
    Base.metadata.create_all(bind=engine)
    logger.info("Base de datos inicializada")
    yield
    logger.info("TaskFlow apagándose")


app = FastAPI(
    title="TaskFlow API",
    description="Gestión de tareas con FastAPI + AWS",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)"
    )
    return response


# Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/index.html") as f:
        return f.read()


# Routers
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
