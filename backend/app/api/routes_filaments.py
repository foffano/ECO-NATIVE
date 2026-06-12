from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.db.models import FilamentSpool, ProductionSettings, now_iso
from backend.app.db.store import store
from backend.app.services.production_cost import get_production_settings

router = APIRouter()


class ProductionSettingsUpdate(BaseModel):
    electricity_kwh_price_brl: float = Field(ge=0)
    printer_power_watts: float = Field(ge=0)


class FilamentCreate(BaseModel):
    name: str
    material: str = "PLA"
    color: str | None = None
    spool_price_brl: float = Field(ge=0)
    spool_weight_g: float = Field(default=1000, gt=0)
    notes: str | None = None


class FilamentUpdate(BaseModel):
    name: str | None = None
    material: str | None = None
    color: str | None = None
    spool_price_brl: float | None = Field(default=None, ge=0)
    spool_weight_g: float | None = Field(default=None, gt=0)
    notes: str | None = None


def _get_store_profile_or_404(store_profile_id: str):
    state = store.load()
    profile = next((item for item in state.store_profiles if item.id == store_profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de loja nao encontrado")
    return state, profile


@router.get("/{store_profile_id}/filaments")
def list_filaments(store_profile_id: str) -> list[FilamentSpool]:
    state, _ = _get_store_profile_or_404(store_profile_id)
    items = [item for item in state.filament_spools if item.store_profile_id == store_profile_id]
    return sorted(items, key=lambda item: item.name.lower())


@router.post("/{store_profile_id}/filaments")
def create_filament(store_profile_id: str, payload: FilamentCreate) -> FilamentSpool:
    state, _ = _get_store_profile_or_404(store_profile_id)
    spool = FilamentSpool(store_profile_id=store_profile_id, **payload.model_dump())
    state.filament_spools.append(spool)
    store.save(state)
    return spool


@router.patch("/{store_profile_id}/filaments/{filament_id}")
def update_filament(store_profile_id: str, filament_id: str, payload: FilamentUpdate) -> FilamentSpool:
    state, _ = _get_store_profile_or_404(store_profile_id)
    spool = next(
        (
            item
            for item in state.filament_spools
            if item.id == filament_id and item.store_profile_id == store_profile_id
        ),
        None,
    )
    if not spool:
        raise HTTPException(status_code=404, detail="Filamento nao encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(spool, key, value)
    spool.updated_at = now_iso()
    store.save(state)
    return spool


@router.delete("/{store_profile_id}/filaments/{filament_id}")
def delete_filament(store_profile_id: str, filament_id: str) -> dict:
    state, _ = _get_store_profile_or_404(store_profile_id)
    spool = next(
        (
            item
            for item in state.filament_spools
            if item.id == filament_id and item.store_profile_id == store_profile_id
        ),
        None,
    )
    if not spool:
        raise HTTPException(status_code=404, detail="Filamento nao encontrado")
    state.filament_spools = [item for item in state.filament_spools if item.id != filament_id]
    store.save(state)
    return {"status": "deleted", "filament_id": filament_id}


@router.get("/{store_profile_id}/production-settings")
def read_production_settings(store_profile_id: str) -> ProductionSettings:
    state, _ = _get_store_profile_or_404(store_profile_id)
    return get_production_settings(state, store_profile_id)


@router.put("/{store_profile_id}/production-settings")
def update_production_settings(store_profile_id: str, payload: ProductionSettingsUpdate) -> ProductionSettings:
    state, _ = _get_store_profile_or_404(store_profile_id)
    settings = get_production_settings(state, store_profile_id)
    if settings.store_profile_id not in {item.store_profile_id for item in state.production_settings}:
        state.production_settings.append(settings)
    settings.electricity_kwh_price_brl = payload.electricity_kwh_price_brl
    settings.printer_power_watts = payload.printer_power_watts
    settings.updated_at = now_iso()
    store.save(state)
    return settings
