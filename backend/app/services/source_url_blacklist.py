from backend.app.db.models import BlockedSourceUrl, Product, StudioState
from backend.app.services.makerworld_scraper import clean_makerworld_url


def project_blocked_url_set(state: StudioState, project_id: str) -> set[str]:
    blocked: set[str] = set()
    for entry in state.blocked_source_urls:
        if entry.project_id != project_id:
            continue
        normalized = clean_makerworld_url(entry.url)
        if normalized:
            blocked.add(normalized)
    return blocked


def collect_skip_urls(state: StudioState, project_id: str) -> tuple[set[str], set[str], set[str]]:
    product_urls = {
        clean_makerworld_url(product.source_url)
        for product in state.products
        if product.project_id == project_id and product.source_url
    }
    blocked_urls = project_blocked_url_set(state, project_id)
    skip_urls = product_urls | blocked_urls
    return product_urls, blocked_urls, skip_urls


def add_blocked_source_url(
    state: StudioState,
    project_id: str,
    url: str,
    *,
    reason: str = "deleted",
    label: str | None = None,
) -> BlockedSourceUrl | None:
    normalized = clean_makerworld_url(url)
    if not normalized:
        return None

    for entry in state.blocked_source_urls:
        if entry.project_id != project_id:
            continue
        if clean_makerworld_url(entry.url) != normalized:
            continue
        entry.url = normalized
        if label:
            entry.label = label
        if reason:
            entry.reason = reason
        return entry

    entry = BlockedSourceUrl(
        project_id=project_id,
        url=normalized,
        reason=reason,
        label=label,
    )
    state.blocked_source_urls.append(entry)
    return entry


def block_product_source_url(state: StudioState, product: Product) -> BlockedSourceUrl | None:
    if not product.source_url:
        return None
    return add_blocked_source_url(
        state,
        product.project_id,
        product.source_url,
        reason="deleted",
        label=product.name,
    )


def remove_blocked_source_url(state: StudioState, project_id: str, entry_id: str) -> BlockedSourceUrl | None:
    entry = next(
        (
            item
            for item in state.blocked_source_urls
            if item.id == entry_id and item.project_id == project_id
        ),
        None,
    )
    if not entry:
        return None
    state.blocked_source_urls = [item for item in state.blocked_source_urls if item.id != entry_id]
    return entry
