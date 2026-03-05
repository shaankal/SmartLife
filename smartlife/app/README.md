# SmartLife — Personal Insights REST API

A FastAPI + SQLite API for logging personal metrics (sleep, steps, mood, etc.) and generating insights:
- trends & rolling averages
- correlations
- anomaly flags
- Matplotlib charts as PNG

## Run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
