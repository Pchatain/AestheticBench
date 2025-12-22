"""FastAPI application for MoralBench results viewer."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import annotations, results

app = FastAPI(title="MoralBench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(results.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}
