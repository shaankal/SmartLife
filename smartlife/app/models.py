from sqlalchemy import String, Float, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base

class MetricPoint(Base):
    __tablename__ = "metric_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)  # e.g., "sleep_hours"
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

Index("ix_metric_ts", MetricPoint.metric, MetricPoint.ts)
