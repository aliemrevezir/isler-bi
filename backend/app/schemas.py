"""Pydantic şemaları (API I/O)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str | None = None
    role: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Kullanıcı yönetimi (admin) ---
class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "viewer"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordIn(BaseModel):
    password: str


# --- Jobs ---
class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    title: str
    description: str | None = None
    schedule: str | None = None
    enabled: bool
    depends_on: str | None = None
    created_by: str | None = None
    updated_at: datetime | None = None


class JobCreate(BaseModel):
    key: str
    title: str
    description: str | None = None
    code: str | None = None
    schedule: str | None = None
    depends_on: str | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    schedule: str | None = None
    enabled: bool | None = None
    depends_on: str | None = None


class CodeIn(BaseModel):
    code: str


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_by: str | None = None
    created_at: datetime


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_key: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    rows_out: int | None = None
    log: str | None = None
    error: str | None = None
    triggered_by: str | None = None


# --- Dashboards ---
class DashboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    title: str
    description: str | None = None
    created_by: str | None = None
    updated_at: datetime | None = None


class DashboardCreate(BaseModel):
    key: str
    title: str
    description: str | None = None
    code: str | None = None


class DashboardRunIn(BaseModel):
    filters: dict = {}


# --- Parametreler: cari hedef ---
class CariHedefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cari: str
    duzey: str
    nufus: int | None = None
    perakende_hedef: int | None = None
    kurumsal_hedef: int | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None


class CariHedefIn(BaseModel):
    cari: str
    duzey: str  # ORTAOKUL | LİSE
    nufus: int | None = None
    perakende_hedef: int | None = None
    kurumsal_hedef: int | None = None


# --- Ingest ---
class IngestStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source: str
    last_watermark: str | None = None
    last_run_at: datetime | None = None
    last_status: str | None = None
    rows_last: int | None = None
    error: str | None = None


class IngestRunIn(BaseModel):
    sources: list[str] | None = None  # None → tümü
    mode: str = "incremental"  # incremental | backfill
    from_date: str | None = None  # backfill için YYYY-MM-DD
    to_date: str | None = None
