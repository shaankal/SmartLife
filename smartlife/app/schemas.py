from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class MetricPointCreate(BaseModel):
    ts: datetime
    value: float
    source: str = "manual"
    note: Optional[str] = None

class MetricPointOut(BaseModel):
    id: int
    metric: str
    ts: datetime
    value: float
    source: str
    note: Optional[str] = None

    class Config:
        from_attributes = True

class BulkIngestRequest(BaseModel):
    points: List[MetricPointCreate] = Field(min_length=1)

class StatsResponse(BaseModel):
    metric: str
    count: int
    min: float
    max: float
    mean: float
    std: float

class TrendResponse(BaseModel):
    metric: str
    window: int
    points: List[dict]  # [{"ts":..., "value":..., "rolling":...}]

class CorrelationResponse(BaseModel):
    metric_x: str
    metric_y: str
    n: int
    pearson_r: float | None

class AnomalyItem(BaseModel):
    id: int
    ts: datetime
    value: float
    z: float

class AnomalyResponse(BaseModel):
    metric: str
    threshold: float
    anomalies: list[AnomalyItem]
