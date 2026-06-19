"""FastAPI application entry point for DCA Lab."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .api import search, backtest

app = FastAPI(title="DCA Lab", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")


@app.on_event("startup")
def _startup() -> None:
    db.get_engine()  # create the sqlite file + tables if missing


@app.get("/api/health")
def health():
    return {"ok": True}
