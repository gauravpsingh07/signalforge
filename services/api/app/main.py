from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import error_payload, http_error_handler, validation_error_handler
from app.routes import api_keys, auth, events, health, incidents, metrics, pipeline, projects


settings = get_settings()

app = FastAPI(
    title="SignalForge API",
    description="Foundation API for the SignalForge distributed observability platform.",
    version=settings.version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)


@app.middleware("http")
async def request_size_guard(request: Request, call_next):
    content_length = request.headers.get("content-length")
    try:
        request_size = int(content_length) if content_length else 0
    except ValueError:
        request_size = 0
    if request_size > settings.max_request_body_bytes:
        return JSONResponse(
            status_code=413,
            content=error_payload(
                code="request_too_large",
                message=f"Request body must be {settings.max_request_body_bytes} bytes or fewer",
            ),
        )
    return await call_next(request)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(api_keys.router)
app.include_router(events.router)
app.include_router(incidents.router)
app.include_router(metrics.router)
app.include_router(pipeline.router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": "signalforge-api",
        "status": "ready",
        "version": settings.version,
        "timestamp": datetime.now(UTC).isoformat(),
    }
