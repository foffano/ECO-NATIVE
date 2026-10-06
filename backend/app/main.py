from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from backend.app.api.routes_exports import router as exports_router
from backend.app.api.routes_ai_profiles import router as ai_profiles_router
from backend.app.api.routes_assets import router as assets_router
from backend.app.api.routes_backups import router as backups_router
from backend.app.api.routes_image_options import router as image_options_router
from backend.app.api.routes_jobs import router as jobs_router
from backend.app.api.routes_mercadolivre import callback_router as mercadolivre_callback_router, router as mercadolivre_router
from backend.app.api.routes_products import router as products_router
from backend.app.api.routes_projects import router as projects_router
from backend.app.api.routes_r2 import router as r2_router
from backend.app.api.routes_runtime import router as runtime_router
from backend.app.api.routes_settings import router as settings_router
from backend.app.api.routes_filaments import router as filaments_router
from backend.app.api.routes_store_profiles import router as store_profiles_router
from backend.app.api.routes_auth import COOKIE_NAME, router as auth_router
from backend.app.api.routes_admin import router as admin_router
from backend.app.core.paths import ensure_app_dirs
from backend.app.core.maintenance import maintenance_requested
from backend.app.db.store import store
from backend.app.services.auth import read_session, setup_required
from backend.app.services.authorization import store_project_ids

ensure_app_dirs()

@asynccontextmanager
async def lifespan(app):
    from backend.app.core.server_lock import server_lock
    from backend.app.services.job_queue import job_queue
    from backend.app.services.makerworld_session import close_all_login_sessions
    from backend.app.services.auth import _secret
    with server_lock():
        # Initialize before concurrent requests can create different secrets.
        setup_required()
        _secret()
        job_queue.start()
        try:
            yield
        finally:
            await asyncio.to_thread(close_all_login_sessions)
            await asyncio.to_thread(job_queue.stop)


app = FastAPI(title="ECO Native Studio API", version="0.2.0", docs_url=None, redoc_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _outside_store_scope(path: str, store_profile_id: str | None) -> bool:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3:
        return False
    if parts[1] == "store-profiles":
        return parts[2] != store_profile_id
    if parts[1] not in {"projects", "products", "assets"}:
        return False

    state = store.snapshot()
    project_id: str | None = None
    if parts[1] == "projects":
        project_id = parts[2]
    elif parts[1] == "products":
        product = next((item for item in state.products if item.id == parts[2]), None)
        if not product:
            return False
        project_id = product.project_id
    else:
        found = store.find_asset(parts[2])
        if not found:
            return False
        project_id = found[0].project_id

    project = next((item for item in state.projects if item.id == project_id), None)
    if parts[1] == "projects" and not project:
        return False
    return not project or project.id not in store_project_ids(state, store_profile_id)


class StoreAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"} and maintenance_requested():
            return JSONResponse({"detail": "Servidor em atualização. Tente novamente em instantes."}, status_code=503)
        public = path == "/health" or path.startswith("/api/auth/") or not path.startswith("/api/")
        user = read_session(request.cookies.get(COOKIE_NAME))
        request.state.auth = user
        if public:
            return await call_next(request)
        if setup_required():
            return JSONResponse({"detail": "Configure o primeiro acesso"}, status_code=401)
        if not user:
            return JSONResponse({"detail": "Faça login para continuar"}, status_code=401)

        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
            if origin and urlparse(origin).netloc.casefold() != str(forwarded_host).split(",", 1)[0].strip().casefold():
                return JSONResponse({"detail": "Origem da requisição não permitida"}, status_code=403)

        # Defense in depth for endpoints addressed by object id. List/create routes
        # apply their own store scope below.
        if await run_in_threadpool(_outside_store_scope, path, user.store_profile_id):
            return JSONResponse({"detail": "Recurso não encontrado"}, status_code=404)
        return await call_next(request)


app.add_middleware(StoreAuthenticationMiddleware)


_BINARY_API_PATHS = ("/api/assets/", "/api/backups/download")
_BINARY_API_SUFFIXES = ("/download-files", "/photo", "/frame")


class TextGZipMiddleware:
    """Gzip JSON and frontend bundles; images and archives are already compressed."""

    def __init__(self, app) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=1024)

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "") if scope["type"] == "http" else ""
        binary = path.startswith(_BINARY_API_PATHS) or path.endswith(_BINARY_API_SUFFIXES)
        text = path.startswith("/api/") or path == "/" or path.endswith((".js", ".css", ".html", ".svg", ".json"))
        if text and not binary:
            await self.gzip(scope, receive, send)
        else:
            await self.app(scope, receive, send)


app.add_middleware(TextGZipMiddleware)


@app.get("/health")
def health() -> dict:
    from backend.app.services.job_queue import admission_lock
    from backend.app.services.makerworld_session import active_login_sessions
    # Admission and the maintenance acknowledgement share a lock. Once this
    # response reports maintenance, a new queued job/login cannot slip through.
    with admission_lock:
        maintenance = maintenance_requested()
        payload = {
            "status": "ok", "service": "eco-native-studio-api",
            "version": os.getenv("ECO_NATIVE_VERSION", "dev"),
            "revision": os.getenv("ECO_NATIVE_REVISION", "unknown"),
            "maintenance": maintenance,
        }
        if maintenance:
            payload["active_jobs"] = sum(str(job.status) in {"queued", "running"} for job in store.snapshot().jobs)
            payload["active_login_sessions"] = active_login_sessions()
        return payload


app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(products_router, prefix="/api/products", tags=["products"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
app.include_router(backups_router, prefix="/api/backups", tags=["backups"])
app.include_router(exports_router, prefix="/api/exports", tags=["exports"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(runtime_router, prefix="/api/runtime", tags=["runtime"])
app.include_router(ai_profiles_router, prefix="/api/ai-profiles", tags=["ai-profiles"])
app.include_router(assets_router, prefix="/api/assets", tags=["assets"])
app.include_router(store_profiles_router, prefix="/api/store-profiles", tags=["store-profiles"])
app.include_router(filaments_router, prefix="/api/store-profiles", tags=["filaments"])
app.include_router(image_options_router, prefix="/api/image-options", tags=["image-options"])
app.include_router(r2_router, prefix="/api/r2", tags=["r2"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(mercadolivre_router, prefix="/api/integrations/mercado-livre", tags=["mercado-livre"])
app.include_router(mercadolivre_callback_router, prefix="/api/auth/mercado-livre", tags=["mercado-livre"])

# In production the same local process serves the compiled React application.
# Cloudflare Tunnel therefore exposes one origin while all files and work stay here.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "dist" / "frontend"


class FrontendFiles(StaticFiles):
    """Vite names bundles by content hash, so they can be cached for good; the
    HTML that points at them must be revalidated, or browsers keep running the
    previous release after an update."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            hashed = path.startswith("assets/")
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if hashed else "no-cache"
        return response


if FRONTEND_DIR.exists():
    app.mount("/", FrontendFiles(directory=FRONTEND_DIR, html=True), name="frontend")
