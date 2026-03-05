from __future__ import annotations
from datetime import datetime
from typing import Sequence, Tuple
import numpy as np

def basic_stats(values: Sequence[float]) -> tuple[int, float, float, float, float]:
    arr = np.array(values, dtype=float)
    if arr.size == 0:
        return 0, float("nan"), float("nan"), float("nan"), float("nan")
    return (
        int(arr.size),
        float(arr.min()),
        float(arr.max()),
        float(arr.mean()),
        float(arr.std(ddof=0)),
    )

def rolling_mean(times: Sequence[datetime], values: Sequence[float], window: int) -> list[float | None]:
    """Simple rolling mean over last `window` points (not time-based)."""
    arr = np.array(values, dtype=float)
    out: list[float | None] = []
    for i in range(len(arr)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(float(arr[i+1-window:i+1].mean()))
    return out

def pearson_r(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 2 or len(y) < 2:
        return None
    xv = np.array(x, dtype=float)
    yv = np.array(y, dtype=float)
    if np.std(xv) == 0 or np.std(yv) == 0:
        return None
    return float(np.corrcoef(xv, yv)[0, 1])

def zscore_anomalies(ids: Sequence[int], times: Sequence[datetime], values: Sequence[float], threshold: float):
    arr = np.array(values, dtype=float)
    if arr.size < 2:
        return []
    mu = arr.mean()
    sd = arr.std(ddof=0)
    if sd == 0:
        return []
    z = (arr - mu) / sd
    out = []
    for i, zi in enumerate(z):
        if abs(float(zi)) >= threshold:
            out.append({"id": int(ids[i]), "ts": times[i], "value": float(values[i]), "z": float(zi)})
    return out
