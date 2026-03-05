from __future__ import annotations
from io import BytesIO
from datetime import datetime
from typing import Sequence, Optional
import matplotlib.pyplot as plt

def _png_response(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=140)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

def line_plot(times: Sequence[datetime], values: Sequence[float], title: str, ylabel: str) -> bytes:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(times, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("time")
    fig.autofmt_xdate()
    return _png_response(fig)

def scatter_plot(x: Sequence[float], y: Sequence[float], title: str, xlabel: str, ylabel: str) -> bytes:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    return _png_response(fig)
