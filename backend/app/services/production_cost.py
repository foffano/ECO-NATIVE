from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.db.models import FilamentSpool, ProductionSettings, Product
from backend.app.services.cost_tracker import product_ai_cost_usd
from backend.app.services.print_plates import filament_usage_from_plates, plate_totals, read_print_plates
from backend.app.services.runtime_status import get_exchange_status
from backend.app.services.slice_info import format_print_time


class FilamentUsage(BaseModel):
    filament_id: str
    grams: float = Field(ge=0)


class ExtraProductionCost(BaseModel):
    label: str
    amount_brl: float = Field(ge=0)


class ProductionCost(BaseModel):
    filament_id: str | None = None
    grams: float = Field(default=0, ge=0)
    print_time_minutes: int = Field(default=0, ge=0)
    other_costs_brl: float = Field(default=0, ge=0)
    filaments: list[FilamentUsage] = Field(default_factory=list)
    extra_costs: list[ExtraProductionCost] = Field(default_factory=list)
    notes: str = ""


class FilamentCostLine(BaseModel):
    filament_id: str
    name: str
    material: str
    color: str | None = None
    grams: float
    cost_per_gram_brl: float
    cost_brl: float


class ProductionCostBreakdown(BaseModel):
    production_cost: ProductionCost
    filament_lines: list[FilamentCostLine] = Field(default_factory=list)
    filament_total_brl: float = 0
    energy_cost_brl: float = 0
    depreciation_cost_brl: float = 0
    maintenance_cost_brl: float = 0
    labor_cost_brl: float = 0
    other_costs_brl: float = 0
    extra_total_brl: float = 0
    production_subtotal_brl: float = 0
    ai_cost_usd: float = 0
    ai_cost_brl: float | None = None
    total_brl: float | None = None
    print_time_minutes: int = 0
    print_time_label: str = "—"
    plate_count: int = 0
    cost_per_hour_brl: float | None = None


def filament_cost_per_gram(spool: FilamentSpool) -> float:
    if spool.spool_weight_g <= 0:
        return 0
    return spool.spool_price_brl / spool.spool_weight_g


def normalize_production_cost(raw: ProductionCost) -> ProductionCost:
    filament_id = raw.filament_id
    grams = raw.grams
    if not filament_id and raw.filaments:
        filament_id = raw.filaments[0].filament_id
        grams = raw.filaments[0].grams
    other_costs_brl = raw.other_costs_brl
    if other_costs_brl <= 0 and raw.extra_costs:
        other_costs_brl = round(sum(item.amount_brl for item in raw.extra_costs), 2)
    return ProductionCost(
        filament_id=filament_id,
        grams=grams,
        print_time_minutes=raw.print_time_minutes,
        other_costs_brl=other_costs_brl,
        filaments=raw.filaments,
        extra_costs=raw.extra_costs,
        notes=raw.notes,
    )


def read_production_cost(product: Product) -> ProductionCost:
    raw = product.metadata.get("production_cost")
    if not isinstance(raw, dict):
        return ProductionCost()
    return normalize_production_cost(ProductionCost.model_validate(raw))


def resolve_production_cost(product: Product) -> ProductionCost:
    stored = read_production_cost(product)
    plates = read_print_plates(product)
    if not plates:
        return stored

    totals = plate_totals(plates)
    grams_by_filament = filament_usage_from_plates(plates)
    filaments = [FilamentUsage(filament_id=filament_id, grams=grams) for filament_id, grams in grams_by_filament.items()]
    single = filaments[0] if len(filaments) == 1 else None
    return ProductionCost(
        filament_id=single.filament_id if single else None,
        grams=single.grams if single else 0,
        print_time_minutes=int(totals["total_print_time_minutes"]),
        other_costs_brl=stored.other_costs_brl,
        filaments=filaments,
        extra_costs=stored.extra_costs,
        notes=stored.notes,
    )


def write_production_cost(product: Product, production_cost: ProductionCost) -> None:
    normalized = normalize_production_cost(production_cost)
    if normalized.filament_id:
        normalized.filaments = [FilamentUsage(filament_id=normalized.filament_id, grams=normalized.grams)]
    product.metadata["production_cost"] = normalized.model_dump()


def default_production_settings(store_profile_id: str) -> ProductionSettings:
    return ProductionSettings(store_profile_id=store_profile_id)


def get_production_settings(state, store_profile_id: str) -> ProductionSettings:
    existing = next((item for item in state.production_settings if item.store_profile_id == store_profile_id), None)
    if existing:
        return existing
    return default_production_settings(store_profile_id)


def energy_cost_brl(print_time_minutes: int, settings: ProductionSettings) -> float:
    if print_time_minutes <= 0 or settings.printer_power_watts <= 0 or settings.electricity_kwh_price_brl <= 0:
        return 0
    hours = print_time_minutes / 60
    kwh = hours * (settings.printer_power_watts / 1000)
    return round(kwh * settings.electricity_kwh_price_brl, 2)


def hourly_cost_brl(print_time_minutes: int, hourly_rate: float) -> float:
    if print_time_minutes <= 0 or hourly_rate <= 0:
        return 0
    return round((print_time_minutes / 60) * hourly_rate, 2)


def depreciation_cost_brl(print_time_minutes: int, settings: ProductionSettings) -> float:
    if settings.printer_purchase_price_brl <= 0 or settings.printer_useful_life_hours <= 0:
        return 0
    hourly_rate = settings.printer_purchase_price_brl / settings.printer_useful_life_hours
    return hourly_cost_brl(print_time_minutes, hourly_rate)


def maintenance_cost_brl(print_time_minutes: int, settings: ProductionSettings) -> float:
    return hourly_cost_brl(print_time_minutes, settings.maintenance_cost_per_hour_brl)


def labor_cost_brl(print_time_minutes: int, settings: ProductionSettings) -> float:
    return hourly_cost_brl(print_time_minutes, settings.labor_cost_per_hour_brl)


def usd_to_brl(usd: float) -> float | None:
    if usd <= 0:
        return 0
    exchange = get_exchange_status(allow_fetch=False)
    rate = exchange.get("usd_brl")
    if rate is None:
        return None
    return round(float(rate) * usd, 2)


def build_production_cost_breakdown(
    product: Product,
    filaments: list[FilamentSpool],
    settings: ProductionSettings,
) -> ProductionCostBreakdown:
    production_cost = resolve_production_cost(product)
    filament_map = {item.id: item for item in filaments}
    lines: list[FilamentCostLine] = []
    filament_total = 0.0

    if production_cost.filament_id and production_cost.grams > 0:
        spool = filament_map.get(production_cost.filament_id)
        if spool:
            cost_per_gram = filament_cost_per_gram(spool)
            line_cost = round(production_cost.grams * cost_per_gram, 2)
            lines.append(
                FilamentCostLine(
                    filament_id=spool.id,
                    name=spool.name,
                    material=spool.material,
                    color=spool.color,
                    grams=production_cost.grams,
                    cost_per_gram_brl=round(cost_per_gram, 4),
                    cost_brl=line_cost,
                )
            )
            filament_total = line_cost
    else:
        for usage in production_cost.filaments:
            spool = filament_map.get(usage.filament_id)
            if not spool:
                continue
            cost_per_gram = filament_cost_per_gram(spool)
            line_cost = round(usage.grams * cost_per_gram, 2)
            lines.append(
                FilamentCostLine(
                    filament_id=spool.id,
                    name=spool.name,
                    material=spool.material,
                    color=spool.color,
                    grams=usage.grams,
                    cost_per_gram_brl=round(cost_per_gram, 4),
                    cost_brl=line_cost,
                )
            )
            filament_total += line_cost

    energy_total = energy_cost_brl(production_cost.print_time_minutes, settings)
    depreciation_total = depreciation_cost_brl(production_cost.print_time_minutes, settings)
    maintenance_total = maintenance_cost_brl(production_cost.print_time_minutes, settings)
    labor_total = labor_cost_brl(production_cost.print_time_minutes, settings)
    other_total = round(production_cost.other_costs_brl, 2)
    legacy_extra = round(sum(item.amount_brl for item in production_cost.extra_costs), 2)
    if other_total <= 0 and legacy_extra > 0:
        other_total = legacy_extra
    ai_cost_usd = round(product_ai_cost_usd(product), 4)
    ai_cost_brl = usd_to_brl(ai_cost_usd)
    production_subtotal = round(
        filament_total + energy_total + depreciation_total + maintenance_total + labor_total + other_total,
        2,
    )
    total_brl = round(production_subtotal + (ai_cost_brl or 0), 2) if ai_cost_brl is not None else None
    print_minutes = production_cost.print_time_minutes
    cost_per_hour = round((production_subtotal / (print_minutes / 60)), 2) if print_minutes > 0 else None
    plates = read_print_plates(product)

    return ProductionCostBreakdown(
        production_cost=production_cost,
        filament_lines=lines,
        filament_total_brl=round(filament_total, 2),
        energy_cost_brl=energy_total,
        depreciation_cost_brl=depreciation_total,
        maintenance_cost_brl=maintenance_total,
        labor_cost_brl=labor_total,
        other_costs_brl=other_total,
        extra_total_brl=other_total,
        production_subtotal_brl=production_subtotal,
        ai_cost_usd=ai_cost_usd,
        ai_cost_brl=ai_cost_brl,
        total_brl=total_brl,
        print_time_minutes=print_minutes,
        print_time_label=format_print_time(print_minutes * 60 if print_minutes else None),
        plate_count=len(plates),
        cost_per_hour_brl=cost_per_hour,
    )
