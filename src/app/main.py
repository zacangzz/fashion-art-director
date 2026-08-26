import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.dependencies import get_db_manager
from app.api import moodboard, generation, history, export, inpaint, refinement, wardrobe, telemetry
from app.utils.telemetry import (
    set_current_request_id,
    generate_request_id,
    TelemetryLogger,
)

from app.utils.logger import setup_logging, get_logger

# Initialize structured logging
setup_logging()
logger = get_logger("main")
telemetry_logger = TelemetryLogger(component="api")

settings = get_settings()


class GetOnlyStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        if scope["method"] not in ("GET", "HEAD"):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure storage folders and DB schema exist
    logger.info("Starting Image Gen Pipeline Studio backend...")
    settings.ensure_directories()
    db_manager = get_db_manager()
    await db_manager.init_db()
    logger.info(f"Studio backend ready. Vision model: '{settings.VISION_MODEL}', Imagen model: '{settings.IMAGEN_MODEL}'")
    yield
    logger.info("Studio backend shutting down.")


app = FastAPI(
    title="Image Gen Pipeline Studio API",
    description="Backend API for Vision Analysis, JSON Graph Studio & Seed-Locked Image Generation",
    version="2.0.0",
    lifespan=lifespan,
)

# Request/Response Logging & Tracing Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    path = request.url.path
    method = request.method

    # Extract or generate request ID
    req_id = request.headers.get("X-Request-ID") or generate_request_id("req")
    set_current_request_id(req_id)

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        response.headers["X-Request-ID"] = req_id

        # Log and audit API requests
        if path.startswith("/api") or path == "/health":
            logger.info(f"{method} {path} -> {response.status_code} ({process_time:.1f}ms)")
            if path.startswith("/api") and not path.startswith("/api/telemetry"):
                telemetry_logger.record_event(
                    event="api_response",
                    request_id=req_id,
                    component="api",
                    status="success" if response.status_code < 400 else "error",
                    duration_ms=process_time,
                    inputs={"method": method, "path": path, "query_params": dict(request.query_params)},
                    outputs={"status_code": response.status_code},
                )
        return response
    except Exception as exc:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"{method} {path} FAILED after {process_time:.1f}ms: {exc}", exc_info=True)
        if path.startswith("/api"):
            telemetry_logger.record_event(
                event="api_error",
                request_id=req_id,
                component="api",
                status="error",
                duration_ms=process_time,
                inputs={"method": method, "path": path, "query_params": dict(request.query_params)},
                error=str(exc),
            )
        raise
    finally:
        set_current_request_id(None)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:7860", "http://127.0.0.1:7860", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(moodboard.router)
app.include_router(generation.router)
app.include_router(history.router)
app.include_router(export.router)
app.include_router(inpaint.router)
app.include_router(refinement.router)
app.include_router(wardrobe.router)
app.include_router(telemetry.router)

# Mount static images directory
gen_storage_dir = os.path.join(settings.STORAGE_DIR, "generations")
os.makedirs(gen_storage_dir, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=gen_storage_dir), name="images")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "title": app.title,
        "version": app.version,
    }


frontend_dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
index_file = os.path.join(frontend_dist_dir, "index.html")


@app.get("/telemetry", response_class=HTMLResponse)
@app.get("/observability", response_class=HTMLResponse)
async def serve_telemetry_page():
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head><title>Observability & Telemetry - Studio</title></head>
        <body style="background:#090b10;color:#f8fafc;font-family:sans-serif;text-align:center;padding:50px;">
            <h2>Studio Observability & Telemetry (Dev Server)</h2>
            <p>Please open the frontend dev server at <a style="color:#6366f1;font-weight:bold;" href="http://localhost:5173/telemetry">http://localhost:5173/telemetry</a></p>
        </body>
        </html>
        """
    )


# Mount built frontend SPA if src/frontend/dist exists, else provide informative index landing page
if os.path.exists(frontend_dist_dir) and os.path.exists(index_file):
    app.mount("/", GetOnlyStaticFiles(directory=frontend_dist_dir, html=True), name="static_frontend")
else:
    @app.get("/", response_class=HTMLResponse)
    async def fallback_index():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Image Gen Pipeline Studio - Backend Ready</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1117; color: #f8fafc; padding: 40px; text-align: center; }
                .card { background: #1a1d26; border: 1px solid #2e3345; border-radius: 12px; max-width: 600px; margin: 40px auto; padding: 30px; }
                h1 { color: #6366f1; font-size: 1.5rem; }
                p { color: #94a3b8; line-height: 1.6; }
                code { background: #000; padding: 3px 8px; border-radius: 4px; color: #38bdf8; font-family: monospace; }
                a { color: #6366f1; text-decoration: none; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Image Gen Pipeline Studio API is Running</h1>
                <p>The backend API is active on port <code>7860</code>. To launch the interactive Frontend Studio:</p>
                <p><strong>Option A (Development):</strong> Run <code>npm run dev</code> inside <code>src/frontend/</code> and open <a href="http://localhost:5173">http://localhost:5173</a></p>
                <p><strong>Option B (Production):</strong> Run <code>npm run build</code> inside <code>src/frontend/</code> and refresh this page.</p>
                <p><a href="/health">Check Health Status</a> &bull; <a href="/telemetry">Observability & Telemetry</a> &bull; <a href="/docs">Interactive API Docs</a></p>
            </div>
        </body>
        </html>
        """

