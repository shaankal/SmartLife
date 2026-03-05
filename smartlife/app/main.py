from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from datetime import datetime
from typing import Optional

from .db import Base, engine, get_db
from .models import MetricPoint
from .schemas import (
    MetricPointCreate, MetricPointOut, BulkIngestRequest,
    StatsResponse, TrendResponse, CorrelationResponse,
    AnomalyResponse, AnomalyItem,
)
from .analytics import basic_stats, rolling_mean, pearson_r, zscore_anomalies
from .plots import line_plot, scatter_plot

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartLife — Personal Insights REST API", version="1.0.0")

# 1) Health
@app.get("/health")
def health():
    return {"status": "ok"}

# 2) List metrics
@app.get("/v1/metrics")
def list_metrics(db: Session = Depends(get_db)):
    rows = db.execute(select(MetricPoint.metric).distinct().order_by(MetricPoint.metric)).all()
    return {"metrics": [r[0] for r in rows]}

# 3) Create point
@app.post("/v1/metrics/{metric}/points", response_model=MetricPointOut)
def create_point(metric: str, body: MetricPointCreate, db: Session = Depends(get_db)):
    p = MetricPoint(metric=metric, ts=body.ts, value=body.value, source=body.source, note=body.note)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

# 4) Bulk ingest points
@app.post("/v1/metrics/{metric}/points/bulk")
def bulk_ingest(metric: str, body: BulkIngestRequest, db: Session = Depends(get_db)):
    objs = [MetricPoint(metric=metric, ts=pt.ts, value=pt.value, source=pt.source, note=pt.note) for pt in body.points]
    db.add_all(objs)
    db.commit()
    return {"inserted": len(objs)}

# 5) Get points (with optional time filter + limit)
@app.get("/v1/metrics/{metric}/points", response_model=list[MetricPointOut])
def get_points(
    metric: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    q = select(MetricPoint).where(MetricPoint.metric == metric)
    if start:
        q = q.where(MetricPoint.ts >= start)
    if end:
        q = q.where(MetricPoint.ts <= end)
    q = q.order_by(MetricPoint.ts.asc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return rows

# 6) Get single point
@app.get("/v1/points/{point_id}", response_model=MetricPointOut)
def get_point(point_id: int, db: Session = Depends(get_db)):
    p = db.get(MetricPoint, point_id)
    if not p:
        raise HTTPException(status_code=404, detail="Point not found")
    return p

# 7) Delete single point
@app.delete("/v1/points/{point_id}")
def delete_point(point_id: int, db: Session = Depends(get_db)):
    p = db.get(MetricPoint, point_id)
    if not p:
        raise HTTPException(status_code=404, detail="Point not found")
    db.delete(p)
    db.commit()
    return {"deleted": point_id}

# 8) Delete all points for metric
@app.delete("/v1/metrics/{metric}/points")
def delete_metric_points(metric: str, db: Session = Depends(get_db)):
    res = db.execute(delete(MetricPoint).where(MetricPoint.metric == metric))
    db.commit()
    return {"deleted_rows": res.rowcount or 0}

# 9) Summary stats
@app.get("/v1/metrics/{metric}/stats", response_model=StatsResponse)
def metric_stats(metric: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(MetricPoint.value).where(MetricPoint.metric == metric).order_by(MetricPoint.ts.asc())
    ).all()
    values = [r[0] for r in rows]
    n, mn, mx, mean, std = basic_stats(values)
    if n == 0:
        raise HTTPException(status_code=404, detail="No data for metric")
    return StatsResponse(metric=metric, count=n, min=mn, max=mx, mean=mean, std=std)

# 10) Trend + rolling average
@app.get("/v1/metrics/{metric}/trend", response_model=TrendResponse)
def metric_trend(metric: str, window: int = Query(7, ge=2, le=365), db: Session = Depends(get_db)):
    rows = db.execute(
        select(MetricPoint.ts, MetricPoint.value).where(MetricPoint.metric == metric).order_by(MetricPoint.ts.asc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No data for metric")
    times = [r[0] for r in rows]
    values = [float(r[1]) for r in rows]
    roll = rolling_mean(times, values, window)
    out = [{"ts": times[i], "value": values[i], "rolling": roll[i]} for i in range(len(values))]
    return TrendResponse(metric=metric, window=window, points=out)

# 11) Correlation between two metrics (paired by timestamp date bucket)
@app.get("/v1/correlations", response_model=CorrelationResponse)
def correlation(
    metric_x: str = Query(...),
    metric_y: str = Query(...),
    bucket: str = Query("day", pattern="^(day|hour)$"),
    db: Session = Depends(get_db),
):
    # naive bucketing: join by YYYY-MM-DD (or hour) string in python
    rows_x = db.execute(
        select(MetricPoint.ts, MetricPoint.value).where(MetricPoint.metric == metric_x)
    ).all()
    rows_y = db.execute(
        select(MetricPoint.ts, MetricPoint.value).where(MetricPoint.metric == metric_y)
    ).all()

    def key(ts: datetime) -> str:
        if bucket == "hour":
            return ts.strftime("%Y-%m-%d %H")
        return ts.strftime("%Y-%m-%d")

    map_x = {}
    for ts, val in rows_x:
        map_x[key(ts)] = float(val)
    map_y = {}
    for ts, val in rows_y:
        map_y[key(ts)] = float(val)

    keys = sorted(set(map_x.keys()) & set(map_y.keys()))
    xs = [map_x[k] for k in keys]
    ys = [map_y[k] for k in keys]
    r = pearson_r(xs, ys)
    return CorrelationResponse(metric_x=metric_x, metric_y=metric_y, n=len(keys), pearson_r=r)

# 12) Anomaly flags (z-score)
@app.get("/v1/metrics/{metric}/anomalies", response_model=AnomalyResponse)
def anomalies(metric: str, threshold: float = Query(2.5, ge=0.5, le=10.0), db: Session = Depends(get_db)):
    rows = db.execute(
        select(MetricPoint.id, MetricPoint.ts, MetricPoint.value)
        .where(MetricPoint.metric == metric)
        .order_by(MetricPoint.ts.asc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No data for metric")
    ids = [r[0] for r in rows]
    times = [r[1] for r in rows]
    vals = [float(r[2]) for r in rows]
    anoms = zscore_anomalies(ids, times, vals, threshold)
    return AnomalyResponse(
        metric=metric,
        threshold=threshold,
        anomalies=[AnomalyItem(**a) for a in anoms],
    )

# 13) Line chart for a metric (PNG)
@app.get("/v1/metrics/{metric}/plot.png")
def metric_plot(metric: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(MetricPoint.ts, MetricPoint.value).where(MetricPoint.metric == metric).order_by(MetricPoint.ts.asc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No data for metric")
    times = [r[0] for r in rows]
    values = [float(r[1]) for r in rows]
    png = line_plot(times, values, title=f"{metric} over time", ylabel=metric)
    return Response(content=png, media_type="image/png")

# 14) Scatter plot for correlation (PNG)
@app.get("/v1/correlations/plot.png")
def correlation_plot(
    metric_x: str = Query(...),
    metric_y: str = Query(...),
    bucket: str = Query("day", pattern="^(day|hour)$"),
    db: Session = Depends(get_db),
):
    # reuse same join logic
    rows_x = db.execute(select(MetricPoint.ts, MetricPoint.value).where(MetricPoint.metric == metric_x)).all()
    rows_y = db.execute(select(MetricPoint.ts, MetricPoint.value).where(MetricPoint.metric == metric_y)).all()

    def key(ts: datetime) -> str:
        if bucket == "hour":
            return ts.strftime("%Y-%m-%d %H")
        return ts.strftime("%Y-%m-%d")

    map_x = {key(ts): float(v) for ts, v in rows_x}
    map_y = {key(ts): float(v) for ts, v in rows_y}

    keys = sorted(set(map_x.keys()) & set(map_y.keys()))
    if len(keys) < 2:
        raise HTTPException(status_code=400, detail="Not enough aligned data for plot")
    xs = [map_x[k] for k in keys]
    ys = [map_y[k] for k in keys]

    png = scatter_plot(xs, ys, title=f"{metric_x} vs {metric_y}", xlabel=metric_x, ylabel=metric_y)
    return Response(content=png, media_type="image/png")
