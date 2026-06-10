from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes_exports import router as exports_router
from backend.app.api.routes_ai_profiles import router as ai_profiles_router
from backend.app.api.routes_assets import router as assets_router
from backend.app.api.routes_backups import router as backups_router
from backend.app.api.routes_image_options import router as image_options_router
from backend.app.api.routes_jobs import router as jobs_router
from backend.app.api.routes_products import router as products_router
from backend.app.api.routes_projects import router as projects_router
from backend.app.api.routes_runtime import router as runtime_router
from backend.app.api.routes_settings import router as settings_router
from backend.app.api.routes_store_profiles import router as store_profiles_router
from backend.app.core.paths import ensure_app_dirs

ensure_app_dirs()

app = FastAPI(title="ECO Native Studio API", version="0.1.0")

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
app.include_router(image_options_router, prefix="/api/image-options", tags=["image-options"])
