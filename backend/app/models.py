"""app şeması SQLAlchemy modelleri."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import SCHEMA_APP, Base

ROLES = ("admin", "analyst", "viewer")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    """raw → derived dönüştürücü. Kod editable (Monaco), run(ctx) sözleşmesi."""
    __tablename__ = "jobs"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text, default="")
    schedule: Mapped[str | None] = mapped_column(String(120))  # cron ifadesi (opsiyonel)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    depends_on: Mapped[str | None] = mapped_column(String(64))  # ingest bitince zincir (opsiyonel)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["JobVersion"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobVersion.id.desc()"
    )


class JobVersion(Base):
    __tablename__ = "job_versions"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_key: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA_APP}.jobs.key", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="versions")


class JobRun(Base):
    """Her çalıştırma audit kaydı + log."""
    __tablename__ = "job_runs"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|success|error
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_out: Mapped[int | None] = mapped_column(Integer)
    log: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[str | None] = mapped_column(Text)  # JSON: canlı ilerleme (yüzde/mesaj/adım)
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(String(64))
    celery_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dashboard(Base):
    """derived → görselleştirme. filter_schema()+run(ctx)→{kpis,charts,table}."""
    __tablename__ = "dashboards"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["DashboardVersion"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan", order_by="DashboardVersion.id.desc()"
    )


class DashboardVersion(Base):
    __tablename__ = "dashboard_versions"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dashboard_key: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA_APP}.dashboards.key", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dashboard: Mapped["Dashboard"] = relationship(back_populates="versions")


class IngestState(Base):
    """Her kaynak için son watermark (incremental delta)."""
    __tablename__ = "ingest_state"
    __table_args__ = {"schema": SCHEMA_APP}

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_watermark: Mapped[str | None] = mapped_column(String(64))  # ISO tarih ya da LOGICALREF
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))
    rows_last: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class IngestRun(Base):
    """Ingest çalıştırma audit kaydı."""
    __tablename__ = "ingest_runs"
    __table_args__ = {"schema": SCHEMA_APP}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sources: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16))  # incremental|backfill
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_out: Mapped[int | None] = mapped_column(Integer)
    log: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[str | None] = mapped_column(Text)  # JSON: canlı ilerleme (kaynak/yüzde/satır)
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Permission(Base):
    """Kaynak-bazlı izin. resource_type: job|dashboard|ingest, resource_key: '*' veya belirli key."""
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("resource_type", "resource_key", "role", name="uq_perm"),
        {"schema": SCHEMA_APP},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_key: Mapped[str] = mapped_column(String(64), default="*")
    role: Mapped[str] = mapped_column(String(16))
    can_view: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    can_run: Mapped[bool] = mapped_column(Boolean, default=False)
