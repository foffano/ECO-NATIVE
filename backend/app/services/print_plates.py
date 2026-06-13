from __future__ import annotations

from backend.app.db.models import PrintPlate, Product


def read_print_plates(product: Product) -> list[PrintPlate]:
    raw = product.metadata.get("print_plates")
    if not isinstance(raw, list):
        return []
    plates: list[PrintPlate] = []
    for item in raw:
        if isinstance(item, dict):
            plates.append(PrintPlate.model_validate(item))
    return plates


def write_print_plates(product: Product, plates: list[PrintPlate]) -> None:
    product.metadata["print_plates"] = [plate.model_dump() for plate in plates]


def plate_totals(plates: list[PrintPlate]) -> dict[str, float | int]:
    total_time = sum(plate.print_time_minutes * plate.quantity for plate in plates)
    total_grams = sum(plate.filament_grams * plate.quantity for plate in plates)
    return {
        "plate_count": len(plates),
        "total_print_time_minutes": total_time,
        "total_filament_grams": round(total_grams, 2),
    }


def filament_usage_from_plates(plates: list[PrintPlate]) -> dict[str, float]:
    grams_by_filament: dict[str, float] = {}
    for plate in plates:
        if not plate.filament_id or plate.filament_grams <= 0:
            continue
        grams_by_filament[plate.filament_id] = grams_by_filament.get(plate.filament_id, 0) + (
            plate.filament_grams * plate.quantity
        )
    return {filament_id: round(grams, 2) for filament_id, grams in grams_by_filament.items()}
