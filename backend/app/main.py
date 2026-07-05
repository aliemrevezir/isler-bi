"""FastAPI uygulaması: auth, ingest, jobs, dashboards, tables router'ları."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, dashboards, ingest, jobs, params, tables, users

# Performans ölçüm logları (isler.perf) uvicorn çıktısında görünsün.
logging.getLogger("isler.perf").setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="İşler Veri Platformu", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(dashboards.router, prefix="/api/dashboards", tags=["dashboards"])
app.include_router(tables.router, prefix="/api/tables", tags=["tables"])
app.include_router(params.router, prefix="/api/params", tags=["params"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
