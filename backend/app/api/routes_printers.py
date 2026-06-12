from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.db.models import Printer3D, now_iso
from backend.app.db.store import store

router = APIRouter()


class PrinterCreate(BaseModel):
    name: str
    model: str | None = None
    notes: str | None = None
    active: bool = True


class PrinterUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    notes: str | None = None
    active: bool | None = None


@router.get("")
def list_printers() -> list[Printer3D]:
    state = store.load()
    return sorted(state.printers_3d, key=lambda item: item.name.lower())


@router.post("")
def create_printer(payload: PrinterCreate) -> Printer3D:
    state = store.load()
    printer = Printer3D(**payload.model_dump())
    state.printers_3d.append(printer)
    store.save(state)
    return printer


@router.patch("/{printer_id}")
def update_printer(printer_id: str, payload: PrinterUpdate) -> Printer3D:
    state = store.load()
    printer = next((item for item in state.printers_3d if item.id == printer_id), None)
    if not printer:
        raise HTTPException(status_code=404, detail="Impressora nao encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(printer, key, value)
    printer.updated_at = now_iso()
    store.save(state)
    return printer


@router.delete("/{printer_id}")
def delete_printer(printer_id: str) -> dict:
    state = store.load()
    printer = next((item for item in state.printers_3d if item.id == printer_id), None)
    if not printer:
        raise HTTPException(status_code=404, detail="Impressora nao encontrada")
    state.printers_3d = [item for item in state.printers_3d if item.id != printer_id]
    state.print_schedule_tasks = [
        item for item in state.print_schedule_tasks if item.printer_id != printer_id
    ]
    store.save(state)
    return {"status": "deleted", "printer_id": printer_id}
