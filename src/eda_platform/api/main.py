"""FastAPI application entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eda_platform.api.routes import (
    architect,
    firmware,
    librarian,
    manifests,
    operations,
    validate,
)

app = FastAPI(
    title="EDA Platform API",
    description="Validation, manifest catalog, template layout, and firmware generation",
    version="0.4.0",
)

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(validate.router)
app.include_router(manifests.router)
app.include_router(librarian.router)
app.include_router(architect.router)
app.include_router(firmware.router)
app.include_router(operations.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
