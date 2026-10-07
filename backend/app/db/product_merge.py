"""Three-way merge of a product written by a long-running job.

A job works on a copy of the product for minutes. Writing that copy back
whole would undo whatever the user (or another job) saved meanwhile, so only
what the job itself changed since `base` is applied onto the stored product.
"""
from collections.abc import Callable
from typing import Any, TypeVar

from backend.app.db.models import Product

T = TypeVar("T")
_MISSING = object()
# Merged by item, not replaced: other jobs may append to them concurrently.
_ID_LIST_METADATA = {"cost_events"}


def _merge_by_key(base: list[T], mine: list[T], theirs: list[T], key: Callable[[T], Any]) -> list[T]:
    base_by_key = {key(item): item for item in base}
    mine_by_key = {key(item): item for item in mine}
    removed = {k for k in base_by_key if k not in mine_by_key}
    changed = {k: item for k, item in mine_by_key.items() if k in base_by_key and item != base_by_key[k]}
    merged = [changed.get(key(item), item) for item in theirs if key(item) not in removed]
    present = {key(item) for item in merged}
    merged.extend(item for k, item in mine_by_key.items() if k not in base_by_key and k not in present)
    return merged


def merge_product(base: Product, mine: Product, theirs: Product) -> Product:
    """`theirs` (the stored product, modified in place) plus the changes from `base` to `mine`."""
    for field in Product.model_fields:
        if field in {"id", "assets", "metadata", "created_at", "updated_at"}:
            continue
        if getattr(mine, field) != getattr(base, field):
            setattr(theirs, field, getattr(mine, field))

    theirs.assets = _merge_by_key(base.assets, mine.assets, theirs.assets, lambda asset: asset.id)

    metadata = dict(theirs.metadata)
    for key in set(base.metadata) | set(mine.metadata):
        mine_value = mine.metadata.get(key, _MISSING)
        base_value = base.metadata.get(key, _MISSING)
        if key in _ID_LIST_METADATA:
            metadata[key] = _merge_by_key(
                list(base_value if isinstance(base_value, list) else []),
                list(mine_value if isinstance(mine_value, list) else []),
                list(metadata.get(key) or []),
                lambda item: (item.get("id") if isinstance(item, dict) else None) or repr(item),
            )
        elif mine_value != base_value:
            if mine_value is _MISSING:
                metadata.pop(key, None)
            else:
                metadata[key] = mine_value
    if "cost_events" in metadata:
        metadata["cost_total_usd"] = round(
            sum(float(item.get("cost_usd") or 0) for item in metadata["cost_events"] if isinstance(item, dict)), 6
        )
    theirs.metadata = metadata
    return theirs
