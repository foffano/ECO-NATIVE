from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.db.models import PrintScheduleStatus, PrintScheduleTask, StudioState, now_iso
from backend.app.db.store import store
from backend.app.services.print_plates import read_print_plates

router = APIRouter()


class ScheduleTaskCreate(BaseModel):
    printer_id: str
    scheduled_date: str
    start_time: str
    duration_minutes: int = Field(default=0, ge=0)
    product_id: str | None = None
    plate_id: str | None = None
    title: str
    quantity: int = Field(default=1, ge=1)
    notes: str = ""
    status: PrintScheduleStatus = PrintScheduleStatus.planned


class ScheduleTaskUpdate(BaseModel):
    printer_id: str | None = None
    scheduled_date: str | None = None
    start_time: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    product_id: str | None = None
    plate_id: str | None = None
    title: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    notes: str | None = None
    status: PrintScheduleStatus | None = None


def _resolve_duration(
    state,
    product_id: str | None,
    plate_id: str | None,
    quantity: int,
    duration_minutes: int,
) -> int:
    if duration_minutes > 0:
        return duration_minutes
    if not product_id or not plate_id:
        return duration_minutes
    product = next((item for item in state.products if item.id == product_id), None)
    if not product:
        return duration_minutes
    plate = next((item for item in read_print_plates(product) if item.id == plate_id), None)
    if not plate or plate.print_time_minutes <= 0:
        return duration_minutes
    return plate.print_time_minutes * max(quantity, 1)


def _ensure_printer(state, printer_id: str) -> None:
    printer = next((item for item in state.printers_3d if item.id == printer_id), None)
    if not printer:
        raise HTTPException(status_code=404, detail="Impressora nao encontrada")


@router.get("")
def list_schedule_tasks(
    date: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
) -> list[PrintScheduleTask]:
    state = store.load()
    items = list(state.print_schedule_tasks)
    if date:
        items = [item for item in items if item.scheduled_date == date]
    elif from_date or to_date:
        start = from_date or to_date or ""
        end = to_date or from_date or start
        items = [item for item in items if start <= item.scheduled_date <= end]
    return sorted(items, key=lambda item: (item.scheduled_date, item.start_time, item.created_at))


@router.post("")
def create_schedule_task(payload: ScheduleTaskCreate) -> PrintScheduleTask:
    preview = store.load()
    _ensure_printer(preview, payload.printer_id)

    def apply(state: StudioState) -> PrintScheduleTask:
        _ensure_printer(state, payload.printer_id)
        duration = _resolve_duration(
            state,
            payload.product_id,
            payload.plate_id,
            payload.quantity,
            payload.duration_minutes,
        )
        task = PrintScheduleTask(
            printer_id=payload.printer_id,
            scheduled_date=payload.scheduled_date,
            start_time=payload.start_time,
            duration_minutes=duration,
            product_id=payload.product_id,
            plate_id=payload.plate_id,
            title=payload.title.strip() or "Impressão",
            quantity=payload.quantity,
            notes=payload.notes,
            status=payload.status,
        )
        state.print_schedule_tasks.append(task)
        return task

    return store.mutate(apply)


@router.patch("/{task_id}")
def update_schedule_task(task_id: str, payload: ScheduleTaskUpdate) -> PrintScheduleTask:
    preview = store.load()
    if not next((item for item in preview.print_schedule_tasks if item.id == task_id), None):
        raise HTTPException(status_code=404, detail="Tarefa de impressao nao encontrada")

    def apply(state: StudioState) -> PrintScheduleTask:
        task = next((item for item in state.print_schedule_tasks if item.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Tarefa de impressao nao encontrada")

        updates = payload.model_dump(exclude_unset=True)
        if "printer_id" in updates:
            _ensure_printer(state, updates["printer_id"])
        for key, value in updates.items():
            setattr(task, key, value)

        if task.duration_minutes <= 0:
            task.duration_minutes = _resolve_duration(
                state,
                task.product_id,
                task.plate_id,
                task.quantity,
                0,
            )

        task.updated_at = now_iso()
        return task

    return store.mutate(apply)


@router.delete("/{task_id}")
def delete_schedule_task(task_id: str) -> dict:
    preview = store.load()
    if not next((item for item in preview.print_schedule_tasks if item.id == task_id), None):
        raise HTTPException(status_code=404, detail="Tarefa de impressao nao encontrada")

    def apply(state: StudioState) -> dict:
        task = next((item for item in state.print_schedule_tasks if item.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Tarefa de impressao nao encontrada")
        state.print_schedule_tasks = [item for item in state.print_schedule_tasks if item.id != task_id]
        return {"status": "deleted", "task_id": task_id}

    return store.mutate(apply)
