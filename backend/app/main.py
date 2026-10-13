import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.research import router as research_router
from app.api.routes import router
from app.api.search import router as search_router
from app.core.config import ROOT, get_settings
from app.core.errors import AppError
from app.core.security import RateLimiter, authorized
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    (ROOT / "data").mkdir(exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.vector_index_dir.mkdir(parents=True, exist_ok=True)
    yield
    await engine.dispose()


app = FastAPI(
    title="ResearchLens AI",
    description=(
        "RAG-Powered Research Paper Analysis and Comparison. "
        "Source-grounded research chat, semantic search, summaries and multi-paper comparison."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(search_router)
app.include_router(research_router)
app.state.rate_limiter = RateLimiter()


@app.exception_handler(AppError)
async def expected_error(request: Request, error: AppError):
    return JSONResponse(
        status_code=error.status,
        content={"error": {"code": error.code, "message": error.message, "details": None}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Please check the submitted values.",
                "details": None,
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, error: StarletteHTTPException):
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(error.detail), "details": None}},
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logger.exception("request_failed path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "details": None,
            }
        },
    )


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid4())
    start = time.perf_counter()
    path = request.url.path
    if request.method != "OPTIONS" and path.startswith("/api/v1/") and path != "/api/v1/health":
        if not authorized(request.headers.get("Authorization")):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "A valid API access token is required.",
                        "details": None,
                    }
                },
            )
        expensive = request.method == "POST" and any(
            path.endswith(suffix)
            for suffix in (
                "/messages",
                "/summary",
                "/analyze",
                "/compare",
                "/retry",
                "/rebuild-index",
                "/documents",
            )
        )
        if expensive and not app.state.rate_limiter.allowed(
            request.client.host if request.client else "local"
        ):
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please retry in a minute.",
                        "details": None,
                    }
                },
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - start) * 1000,
    )
    return response


# CORS wraps authentication/rate-limit responses as well as successful requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
