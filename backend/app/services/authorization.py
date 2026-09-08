from fastapi import HTTPException, Request

from backend.app.db.models import Product, Project, StudioState


def current_store_id(request: Request) -> str:
    user = getattr(request.state, "auth", None)
    if not user:
        raise HTTPException(status_code=401, detail="Faça login para continuar")
    if not user.store_profile_id:
        raise HTTPException(status_code=403, detail="Selecione um acesso de loja para esta operação")
    return user.store_profile_id


def require_admin(request: Request) -> None:
    user = getattr(request.state, "auth", None)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso exclusivo do administrador")


def store_project_ids(state: StudioState, store_profile_id: str) -> set[str]:
    profile = next((item for item in state.store_profiles if item.id == store_profile_id), None)
    return {
        project.id
        for project in state.projects
        if project.store_profile_id == store_profile_id
        or (project.store_profile_id is None and profile is not None and project.store == profile.name)
    }


def require_project(state: StudioState, project_id: str, store_profile_id: str) -> Project:
    if project_id not in store_project_ids(state, store_profile_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return next(project for project in state.projects if project.id == project_id)


def require_product(state: StudioState, product_id: str, store_profile_id: str) -> Product:
    allowed_projects = store_project_ids(state, store_profile_id)
    product = next((item for item in state.products if item.id == product_id and item.project_id in allowed_projects), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product
