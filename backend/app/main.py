from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.routes_exports import router as exports_router
from backend.app.api.routes_ai_profiles import router as ai_profiles_router
from backend.app.api.routes_assets import router as assets_router
from backend.app.api.routes_backups import router as backups_router
from backend.app.api.routes_image_options import router as image_options_router
from backend.app.api.routes_jobs import router as jobs_router
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


class StoreAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
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
        state = store.load()
        allowed_projects = store_project_ids(state, user.store_profile_id)
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[1] == "projects":
            project = next((item for item in state.projects if item.id == parts[2]), None)
            if project and project.id not in allowed_projects:
                return JSONResponse({"detail": "Recurso não encontrado"}, status_code=404)
        if len(parts) >= 3 and parts[1] == "products":
            product = next((item for item in state.products if item.id == parts[2]), None)
            if product:
                project = next((item for item in state.projects if item.id == product.project_id), None)
                if not project or project.id not in allowed_projects:
                    return JSONResponse({"detail": "Recurso não encontrado"}, status_code=404)
        if len(parts) >= 3 and parts[1] == "assets":
            product = next((product for product in state.products if any(asset.id == parts[2] for asset in product.assets)), None)
            project = next((item for item in state.projects if product and item.id == product.project_id), None)
            if product and (not project or project.id not in allowed_projects):
                return JSONResponse({"detail": "Recurso não encontrado"}, status_code=404)
        if len(parts) >= 3 and parts[1] == "store-profiles" and parts[2] != user.store_profile_id:
            return JSONResponse({"detail": "Recurso não encontrado"}, status_code=404)
        return await call_next(request)


app.add_middleware(StoreAuthenticationMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "eco-native-studio-api"}


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

# In production the same local process serves the compiled React application.
# Cloudflare Tunnel therefore exposes one origin while all files and work stay here.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "dist" / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
