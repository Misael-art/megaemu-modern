import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from app.core.middleware import LoggingMiddleware, TimingMiddleware
import time

app = FastAPI()
app.add_middleware(LoggingMiddleware)
app.add_middleware(TimingMiddleware)

@app.get("/")
def read_root():
    return {"Hello": "World"}

client = TestClient(app)

def test_logging_middleware(caplog):
    response = client.get("/")
    assert response.status_code == 200
    assert any("method=GET path=/ status_code=200" in record.message for record in caplog.records)

def test_timing_middleware():
    start_time = time.time()
    response = client.get("/")
    duration = time.time() - start_time
    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"]) >= 0