"""SQLite storage for saved scans and farmer feedback (SQLAlchemy 2.x ORM).

Only what is needed is stored: an EXIF-free downscaled copy of the photo, a thumbnail, the
Grad-CAM overlay, the prediction, optional district and feedback. No names, accounts or GPS.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all tables."""


def utcnow() -> datetime:
    """Timezone-aware 'now' in UTC."""
    return datetime.now(UTC)


class Scan(Base):
    """One saved prediction."""

    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    class_id: Mapped[str] = mapped_column(String(80), index=True)
    crop: Mapped[str] = mapped_column(String(40), index=True)
    disease: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float]
    status: Mapped[str] = mapped_column(String(40))
    district: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    crop_hint: Mapped[str | None] = mapped_column(String(40), nullable=True)
    top3: Mapped[list] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(40))
    image_jpeg: Mapped[bytes] = mapped_column(LargeBinary)
    thumb_jpeg: Mapped[bytes] = mapped_column(LargeBinary)
    gradcam_png: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    feedback: Mapped[Feedback | None] = relationship(
        back_populates="scan", cascade="all, delete-orphan", uselist=False
    )


class Feedback(Base):
    """Farmer feedback on one scan ("was this correct?"), kept for future few-shot adaptation."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), unique=True)
    correct: Mapped[bool] = mapped_column(Boolean)
    correct_class_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scan: Mapped[Scan] = relationship(back_populates="feedback")


def init_db(db_url: str) -> sessionmaker:
    """Create the engine and tables; return a session factory."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:  # SQLite needs this for CASCADE
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
