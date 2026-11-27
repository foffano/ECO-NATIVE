from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
import html
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from backend.app.core.playwright_env import configure_playwright_browsers, playwright_install_hint

from backend.app.services.browser_capacity import browser_lease
from backend.app.services import rate_limiter
from backend.app.core.paths import DATA_DIR
from backend.app.db.models import Product, Project, StoreProfile
from backend.app.services.cover_image import download_cover_file
from backend.app.services.product_paths import (
    model_filename,
    product_assets_dir,
    resolve_sku_for_capture,
)

MAKERWORLD_BASE = "https://makerworld.com"
MAKERWORLD_HOME = "https://makerworld.com/pt"

# How long a page or download may take while no check is on screen.
MANUAL_CHECK_SECONDS = 180
# While a Cloudflare check or MakerWorld puzzle is on screen the collect pauses for the user,
# up to this long; after it the page counts as not loaded.
VERIFICATION_MAX_WAIT_SECONDS = 30 * 60
VERIFICATION_PROMPT = (
    "O MakerWorld pediu uma verificação (captcha ou puzzle). A coleta está pausada: "
    "abra o navegador da coleta e resolva. Ela continua sozinha depois."
)
SLOW_RESPONSE_PROMPT = (
    "O site está demorando para responder. Abra o navegador da coleta e verifique "
    "se existe uma solicitação de validação humana."
)
DOWNLOAD_WAIT_NOTE = (
    " O download aguarda por até 3 minutos. Sem resposta nesse prazo, "
    "a coleta continua com as fotos e o anúncio, sem o arquivo 3D."
)
# Model pages open at the same time in the store's collect browser, each in its own tab.
# Two keeps a download running while the next page loads; more adds little and draws
# Cloudflare checks sooner, since every store's browser leaves through the same IP.
DEFAULT_COLLECT_PARALLEL = 2
MAX_COLLECT_PARALLEL = max(1, int(os.getenv("ECO_NATIVE_COLLECT_MAX_PARALLEL", "4")))

STUDIO_BUTTON_TEXT = re.compile(r"Open in Bambu Studio|Abrir no Bambu Studio", re.IGNORECASE)
DOWNLOAD_3MF_TEXT = re.compile(r"^\s*(Download|Baixar) 3MF\s*$", re.IGNORECASE)
REJECT_COOKIES_TEXT = re.compile(r"^(Reject All|Rejeitar todos|Rejeitar tudo|Recusar todos)$", re.IGNORECASE)
# Logged-in model pages have no <h1>; the title lives in .title-for-share and og:title.
MODEL_PAGE_STATE_JS = """() => {
  const text = (element) => ((element && element.textContent) || '').trim();
  const meta = (selector) => ((document.querySelector(selector) || {}).content || '').trim();
  return {
    challenge: Boolean(window._cf_chl_opt),
    heading: text(document.querySelector('h1')) || text(document.querySelector('.title-for-share')),
    og_title: meta("meta[property='og:title']"),
  };
}"""

AttentionCallback = Callable[[str | None], None]

# MakerWorld's own JSON routes, the ones its model page calls. They give a model's data and
# a signed 3MF link without loading the page, using the collect browser's login cookies.
MAKERWORLD_API = "https://makerworld.com/api/v1/design-service"
# Set to "0" to always read model pages, as before the API was used.
USE_MAKERWORLD_API = os.getenv("ECO_NATIVE_MAKERWORLD_API", "1") != "0"
# After this many links in a row that the API refuses, the rest go straight to their pages.
API_GIVE_UP_AFTER = 3
DESIGN_ID = re.compile(r"/models/(\d+)")
PROFILE_ID = re.compile(r"profileId-(\d+)")


class MakerWorldApiUnavailable(RuntimeError):
    """The API could not give this model; its page is read instead."""


class MakerWorldModelMissing(RuntimeError):
    """The model no longer exists: its page would only wait for a title that never comes."""


def _api_json(api, url: str) -> dict:
    response = api.get(url, headers={"accept": "application/json"}, timeout=30_000)
    if "json" not in (response.headers.get("content-type") or ""):
        # A Cloudflare check answers with an HTML page.
        raise MakerWorldApiUnavailable(f"resposta {response.status} sem JSON (verificação do Cloudflare?)")
    data = response.json()
    if not response.ok:
        error = data.get("error") if isinstance(data, dict) else None
        raise MakerWorldApiUnavailable(f"{error or 'erro'} (HTTP {response.status})")
    if not isinstance(data, dict):
        raise MakerWorldApiUnavailable("resposta inesperada")
    return data


def html_to_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", value or "", flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def capture_via_api(
    api,
    project_id: str,
    url: str,
    download_cover: bool,
    download_model: bool,
    sku_candidates: list[Product] | None = None,
    project: Project | None = None,
    store_profile: StoreProfile | None = None,
) -> ScrapedProduct:
    """Read a model and download its 3MF through MakerWorld's JSON routes."""
    match = DESIGN_ID.search(url)
    if not match:
        raise MakerWorldApiUnavailable("link sem o número do modelo")
    try:
        design = _api_json(api, f"{MAKERWORLD_API}/design/{match.group(1)}")
    except MakerWorldApiUnavailable as exc:
        if "(HTTP 404)" in str(exc):
            raise MakerWorldModelMissing("o modelo não existe mais no MakerWorld") from exc
        raise
    title = str(design.get("title") or "").strip()
    if not title:
        raise MakerWorldApiUnavailable("modelo sem título")
    tags = [str(tag).strip() for tag in design.get("tags") or [] if str(tag).strip()]
    image_url = design.get("coverUrl") or None

    sku = None
    if sku_candidates is not None and project and store_profile:
        sku = resolve_sku_for_capture(title, sku_candidates, project, store_profile)

    model_file_path = None
    if download_model and sku:
        profile = PROFILE_ID.search(url)
        instances = design.get("instances") or []
        instance_id = (
            (profile.group(1) if profile else None)
            or design.get("defaultInstanceId")
            or (instances[0].get("id") if instances else None)
        )
        if not instance_id:
            raise MakerWorldApiUnavailable("modelo sem perfil de impressão")
        info = _api_json(api, f"{MAKERWORLD_API}/instance/{instance_id}/f3mf?type=download&fileType=")
        if not info.get("url"):
            raise MakerWorldApiUnavailable("o MakerWorld não devolveu o link do 3MF")
        response = api.get(info["url"], timeout=180_000)
        body = response.body() if response.ok else b""
        if not body.startswith(b"PK"):  # A 3MF is a zip file.
            raise MakerWorldApiUnavailable(f"download do 3MF falhou (HTTP {response.status})")
        product_dir = product_assets_dir(project_id, sku)
        product_dir.mkdir(parents=True, exist_ok=True)
        output_path = product_dir / model_filename(sku, Path(str(info.get("name") or "")).suffix or ".3mf")
        output_path.write_bytes(body)
        model_file_path = str(output_path)

    local_image_path = None
    if download_cover and image_url and sku:
        local_image_path = download_cover_image(project_id, sku, image_url)

    return ScrapedProduct(
        name=title,
        source_url=url,
        tags=tags,
        description=html_to_text(str(design.get("summary") or "")),
        image_url=image_url,
        local_image_path=local_image_path,
        model_file_path=model_file_path,
        sku=sku,
    )


def collect_parallelism(requested: int | None) -> int:
    if requested is None:
        requested = DEFAULT_COLLECT_PARALLEL
    return max(1, min(MAX_COLLECT_PARALLEL, int(requested)))


def wait_for_api_slot(page) -> None:
    """Hold a model read through the API until the shared pace allows it, staying stoppable."""
    def pause(seconds: float) -> None:
        raise_if_stopped()
        page.wait_for_timeout(seconds * 1000)

    rate_limiter.makerworld_api_limiter.acquire(sleep=pause)


def show_api_notice(page) -> None:
    """The collect browser shows a note instead of a blank tab while models come through the API."""
    try:
        page.set_content(
            "<body style='font:16px sans-serif;display:grid;place-items:center;height:90vh;color:#334'>"
            "<p>Coletando pela API do MakerWorld, sem abrir as páginas dos modelos.<br>"
            "Se algum modelo precisar da página, ela abre aqui.</p></body>"
        )
    except (AttributeError, PlaywrightError):
        pass


def wait_for_page_slot(page) -> None:
    """Hold a MakerWorld page load until the shared pace allows it, staying stoppable."""
    def pause(seconds: float) -> None:
        raise_if_stopped()
        page.wait_for_timeout(seconds * 1000)

    rate_limiter.makerworld_page_limiter.acquire(sleep=pause)


@dataclass
class ScrapedProduct:
    name: str
    source_url: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    image_url: str | None = None
    local_image_path: str | None = None
    model_file_path: str | None = None
    model_error: str | None = None
    sku: str | None = None


@dataclass
class DownloadedProductAssets:
    cover_image_path: str | None = None
    model_file_path: str | None = None
    model_error: str | None = None


def clean_makerworld_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if url.startswith("/"):
        url = f"{MAKERWORLD_BASE}{url}"
    return url.split("?")[0]


# The MakerWorld "Peso total" filter is a slider with fixed steps, in grams;
# the top step is "no limit" and goes in the URL as "-".
WEIGHT_STEPS_G = (1, 10, 25, 50, 75, 100, 250, 500, 750, 1000, 2000)


def weight_filter_param(min_weight_g: int | None, max_weight_g: int | None) -> str | None:
    """MakerWorld's total_weight value, or None when the range is the whole slider."""
    low = min_weight_g if min_weight_g in WEIGHT_STEPS_G else WEIGHT_STEPS_G[0]
    high = max_weight_g if max_weight_g in WEIGHT_STEPS_G else None
    if high is not None and high <= low:
        raise ValueError("O peso máximo precisa ser maior que o peso mínimo.")
    if low == WEIGHT_STEPS_G[0] and high is None:
        return None
    return f"{low},{high if high is not None else '-'}"


def build_search_url(keyword: str, min_weight_g: int | None = None, max_weight_g: int | None = None) -> str:
    keyword = keyword.strip()
    if not keyword:
        return MAKERWORLD_HOME
    query = {"keyword": keyword}
    weight = weight_filter_param(min_weight_g, max_weight_g)
    if weight:
        query["total_weight"] = weight
    return f"https://makerworld.com/pt/search/models?{urllib.parse.urlencode(query, quote_via=urllib.parse.quote)}"


def makerworld_profile_dir(store_profile_id: str | None) -> Path:
    safe_store_id = re.sub(r"[^a-zA-Z0-9_-]+", "", store_profile_id or "legacy") or "legacy"
    return DATA_DIR / "browser_data" / "makerworld" / safe_store_id


@contextmanager
def open_makerworld_context(
    playwright,
    headless: bool,
    store_profile_id: str | None = None,
    viewport: dict[str, int] | None = None,
    watch: bool = False,
):
    # Preserve headed mode on both desktop and the Linux virtual display.
    executable = configure_playwright_browsers(playwright)
    if not executable:
        raise RuntimeError(playwright_install_hint())
    user_data_path = makerworld_profile_dir(store_profile_id)
    user_data_path.mkdir(parents=True, exist_ok=True)
    args = ["--disable-blink-features=AutomationControlled"]
    if watch:
        # A loopback DevTools port lets the panel attach its own connection to watch and control
        # this browser while the job keeps driving it.
        args.append("--remote-debugging-port=0")
    with browser_lease(str(user_data_path)):
        port_file = user_data_path / "DevToolsActivePort"
        port_file.unlink(missing_ok=True)
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                executable_path=str(executable),
                headless=False,
                accept_downloads=True,
                viewport=viewport,
                chromium_sandbox=os.getenv("ECO_NATIVE_CHROMIUM_SANDBOX", "false").lower() == "true",
                args=args,
            )
        except PlaywrightError as error:
            if "Executable doesn't exist" in str(error):
                raise RuntimeError(playwright_install_hint()) from error
            raise
        try:
            if watch and store_profile_id:
                # Imported here: makerworld_session imports this module.
                from backend.app.services.makerworld_session import watch_collect_browser

                with watch_collect_browser(store_profile_id, _devtools_endpoint(port_file)):
                    yield context
            else:
                yield context
        finally:
            context.close()


def _devtools_endpoint(port_file: Path, timeout_seconds: float = 5.0) -> str | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            port = port_file.read_text(encoding="utf-8").split()[0]
            if port.isdigit():
                return f"http://127.0.0.1:{port}"
        except (OSError, IndexError):
            pass
        time.sleep(0.1)
    return None


def first_page(context):
    """Reuse the startup tab so the collect browser shows a single window."""
    return context.pages[0] if context.pages else context.new_page()


def is_cloudflare_challenge(page) -> bool:
    try:
        return bool(page.evaluate("() => Boolean(window._cf_chl_opt)"))
    except PlaywrightError:
        return False


class CollectStopped(Exception):
    """The user stopped the collect; never recorded as a failed link."""


# The collect runs in one worker thread, so the stop request is kept per thread
# instead of being passed through every browser helper.
_stop_request = threading.local()


@contextmanager
def stop_when(event: threading.Event | None):
    _stop_request.event = event
    try:
        yield
    finally:
        _stop_request.event = None


def raise_if_stopped() -> None:
    event = getattr(_stop_request, "event", None)
    if event is not None and event.is_set():
        raise CollectStopped("Coleta interrompida pelo usuário")


def has_human_verification(page) -> bool:
    """Look for visible challenge UI; a loaded CAPTCHA script alone is not evidence."""
    if is_cloudflare_challenge(page):
        return True
    try:
        return bool(page.evaluate("""() => {
            const visible = el => {
                const style = getComputedStyle(el);
                return el.getClientRects().length > 0 && style.visibility !== 'hidden'
                    && style.display !== 'none' && style.opacity !== '0';
            };
            const widgets = document.querySelectorAll(
                'iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"], '
                + '[class*="geetest_panel"], [class*="geetest_box"], '
                + '[class*="captcha-container"], [id*="captcha-container"]'
            );
            if ([...widgets].some(visible)) return true;
            const prompt = /verify (that )?you are human|security verification|complete the puzzle|drag.*puzzle|slide.*verif|verifique se você é humano|verificação de segurança|resolva.*quebra-cabeça/i;
            return [...document.querySelectorAll('[role="dialog"], [aria-modal="true"]')]
                .some(el => visible(el) && prompt.test(el.innerText || ''));
        }"""))
    except PlaywrightError:
        return False


def wait_with_help(
    page,
    ready: Callable[[], Any],
    on_attention: AttentionCallback | None = None,
    *,
    timeout_seconds: float = MANUAL_CHECK_SECONDS,
    ask_after_seconds: float = 20.0,
    attention_note: str = "",
    max_pause_seconds: float = VERIFICATION_MAX_WAIT_SECONDS,
) -> Any:
    """Poll ready() until it returns a value, asking the user for help if a check blocks the page.

    Time spent with a check on screen pauses the timeout: the collect waits for the user
    (up to max_pause_seconds per check) and goes on by itself once the check is solved.
    """
    started = time.monotonic()
    paused_seconds = 0.0
    pause_started: float | None = None
    last_notice = None
    try:
        while True:
            raise_if_stopped()
            try:
                value = ready()
            except PlaywrightError:
                value = None  # The page is navigating.
            if value:
                return value
            now = time.monotonic()
            challenge = has_human_verification(page)
            if challenge:
                if pause_started is None:
                    pause_started = now
                if now - pause_started >= max_pause_seconds:
                    return None
            elif pause_started is not None:
                paused_seconds += now - pause_started
                pause_started = None
            elapsed = now - started - paused_seconds
            if not challenge and elapsed >= timeout_seconds:
                return None
            if on_attention:
                if challenge:
                    message = VERIFICATION_PROMPT
                elif elapsed >= ask_after_seconds:
                    message = SLOW_RESPONSE_PROMPT + attention_note
                else:
                    message = None
                if message != last_notice:
                    on_attention(message)
                    last_notice = message
            page.wait_for_timeout(1000)
    finally:
        if last_notice and on_attention:
            on_attention(None)


def model_page_title(page) -> str | None:
    state = page.evaluate(MODEL_PAGE_STATE_JS)
    if state["challenge"]:
        return None
    return state["heading"] or strip_makerworld_title_suffix(state["og_title"]) or None


def strip_makerworld_title_suffix(title: str) -> str:
    # "Soap Holder - Free 3D Print Model - MakerWorld" -> "Soap Holder"
    return re.sub(r"\s+-\s+[^-]*-\s*MakerWorld\s*$", "", title or "").strip()


def discover_model_urls(
    keyword: str,
    scrolls: int = 8,
    headless: bool = False,
    max_urls: int = 200,
    store_profile_id: str | None = None,
    on_attention: AttentionCallback | None = None,
    min_weight_g: int | None = None,
    max_weight_g: int | None = None,
) -> list[str]:
    headless = False
    target_url = build_search_url(keyword, min_weight_g, max_weight_g)
    urls: list[str] = []
    seen: set[str] = set()
    # Com muitos scrolls o usuario quer alcancar produtos mais abaixo na lista.
    # O teto precisa escalar com os scrolls, senao os primeiros links (do topo,
    # normalmente ja capturados) preenchem o limite e os novos nunca retornam.
    effective_max = max(max_urls, max(scrolls, 1) * 30)

    def harvest(page) -> int:
        """Coleta os links visiveis no DOM agora, acumulando sem duplicar."""
        hrefs = page.eval_on_selector_all(
            "a[href*='/models/']",
            """elements => elements
                .map(element => element.getAttribute('href'))
                .filter(Boolean)
            """,
        )
        added = 0
        for href in hrefs:
            if not isinstance(href, str) or not re.search(r"/models/\d+", href):
                continue
            normalized = clean_makerworld_url(href)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
            added += 1
        return added

    with sync_playwright() as playwright, ExitStack() as contexts:
        browser = contexts.enter_context(open_makerworld_context(
            playwright, headless=False, store_profile_id=store_profile_id, watch=True,
        ))
        page = first_page(browser)
        wait_for_page_slot(page)
        page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6000)

        if not wait_with_help(page, lambda: not is_cloudflare_challenge(page), on_attention):
            raise RuntimeError("A verificação de segurança do MakerWorld não foi resolvida a tempo.")

        # Coleta inicial (antes de rolar) e a cada rolagem, para nao perder
        # itens que a lista virtualizada remove do DOM ao sair da tela.
        harvest(page)
        stagnant_rounds = 0
        for _ in range(max(scrolls, 1)):
            raise_if_stopped()
            previous_height = page.evaluate("() => document.body.scrollHeight")
            page.keyboard.press("End")
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(1200)
            harvest(page)
            new_height = page.evaluate("() => document.body.scrollHeight")
            if new_height <= previous_height:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
            if len(urls) >= effective_max or stagnant_rounds >= 5:
                break

        browser.close()

    return urls[:effective_max]


@dataclass
class _LoadingPage:
    url: str
    page: Any
    started_at: float


@dataclass
class _PendingDownload:
    product: "ScrapedProduct"
    download: Any
    page: Any


class _CollectTabs:
    """The collect browser's pages: up to `limit` model pages load or download at once.

    Playwright's sync API is single-threaded, so the job's thread still drives one page at a
    time; the others keep loading and downloading in the browser meanwhile. Each extra page
    opens in its own window, so Chromium keeps painting it and the panel can show it.
    """

    def __init__(self, context, limit: int, store_profile_id: str | None, on_log: Callable[[str], None] | None):
        self.context = context
        self.limit = limit
        self.store_profile_id = store_profile_id
        self.on_log = on_log
        self.free = [first_page(context)]
        self.created = 1
        self.loading: deque[_LoadingPage] = deque()
        self.pending: deque[_PendingDownload] = deque()
        self._targets: dict[int, str] = {}
        self._states: dict[int, str] = {}
        self._current = None
        # When the user last solved a check in this browser, and whether one is open now.
        self.cleared_at = 0.0
        self._checking = False

    @property
    def busy(self) -> int:
        return len(self.loading) + len(self.pending)

    def take_tab(self):
        if self.free:
            return self.free.pop()
        if self.created < self.limit:
            self.created += 1
            page = self._new_window()
            if self.created == 2:
                self._track(self.context.pages[0] if self.context.pages else page)
            self._track(page)
            return page
        return None

    def _new_window(self):
        try:
            cdp = self.context.new_cdp_session(self.context.pages[0])
            try:
                with self.context.expect_page(timeout=10_000) as opened:
                    cdp.send("Target.createTarget", {"url": "about:blank", "newWindow": True})
            finally:
                cdp.detach()
            return opened.value
        except Exception:
            # A tab in the same window still works; its preview just may not refresh.
            return self.context.new_page()

    def _track(self, page) -> None:
        if id(page) in self._targets or not self.store_profile_id:
            return
        try:
            cdp = self.context.new_cdp_session(page)
            try:
                self._targets[id(page)] = cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
            finally:
                cdp.detach()
        except Exception:
            pass

    def mark(self, page, state: str) -> None:
        """Record what a page is doing (loading, reading, downloading, verification, idle) for the panel."""
        self._states[id(page)] = state
        if self.created == 1 or not self.store_profile_id:
            return
        from backend.app.services.makerworld_session import set_collect_tabs

        set_collect_tabs(self.store_profile_id, [
            {"id": target, "state": self._states.get(key, "idle")} for key, target in self._targets.items()
        ])

    def release(self, page) -> None:
        self.free.append(page)
        self.mark(page, "idle")

    def focus(self, page) -> None:
        """Bring the page the job works on to the front, and show that one in the panel."""
        self._current = page
        self.mark(page, "reading")
        if self.created == 1:
            return  # A single page: the panel already shows it.
        try:
            page.bring_to_front()
        except (AttributeError, PlaywrightError):
            pass
        target = self._targets.get(id(page))
        if target and self.store_profile_id:
            from backend.app.services.makerworld_session import set_collect_target

            set_collect_target(self.store_profile_id, target)

    def attention(self, on_attention: AttentionCallback | None) -> AttentionCallback:
        """Pass notices on, slowing down after each check: they come with too many page loads."""
        def notify(message: str | None) -> None:
            if message == VERIFICATION_PROMPT and not self._checking:
                self._checking = True
                if self._current is not None:
                    self.mark(self._current, "verification")
                if self.limit > 1:
                    self.limit -= 1
                    if self.on_log:
                        self.on_log(
                            f"O MakerWorld pediu verificação; a coleta segue com {self.limit} página(s) por vez."
                        )
            elif message != VERIFICATION_PROMPT and self._checking:
                self._checking = False
                self.cleared_at = time.monotonic()
                if self._current is not None:
                    self.mark(self._current, "reading")
            if on_attention:
                on_attention(message)

        return notify


def scrape_product_urls(
    project_id: str,
    urls: list[str],
    headless: bool = False,
    download_cover: bool = True,
    download_model: bool = False,
    sku_reference_products: list[Product] | None = None,
    project: Project | None = None,
    store_profile: StoreProfile | None = None,
    viewport: dict[str, int] | None = None,
    on_product: Callable[[ScrapedProduct], None] | None = None,
    on_failure: Callable[[str, str], None] | None = None,
    on_attention: AttentionCallback | None = None,
    parallel: int | None = 1,
    on_log: Callable[[str], None] | None = None,
    use_api: bool | None = None,
) -> list[ScrapedProduct]:
    """Capture model pages, reporting each product as soon as its files are on disk.

    Each model is first read through MakerWorld's JSON routes with the browser's login
    cookies, without opening its page. Models the API refuses are read from their pages:
    up to `parallel` load or download at the same time, each in its own window of the
    store's browser. A page that never loads is reported through on_failure instead of
    becoming a product, so the link can be collected again later.
    """
    normalized_urls = []
    for url in urls:
        clean_url = clean_makerworld_url(url)
        if clean_url and clean_url not in normalized_urls:
            normalized_urls.append(clean_url)

    if not normalized_urls:
        return []

    products: list[ScrapedProduct] = []
    sku_candidates = list(sku_reference_products or [])
    queue: deque[str] = deque()
    use_api = USE_MAKERWORLD_API if use_api is None else use_api
    with sync_playwright() as playwright, ExitStack() as contexts:
        browser = contexts.enter_context(open_makerworld_context(
            playwright,
            headless=False,
            viewport=viewport,
            store_profile_id=store_profile.id if store_profile else None,
            watch=True,
        ))
        tabs = _CollectTabs(
            browser, collect_parallelism(parallel), store_profile.id if store_profile else None, on_log,
        )
        notify = tabs.attention(on_attention)

        def remember_sku(product: ScrapedProduct) -> None:
            # The next model must not take this SKU.
            if product.sku:
                sku_candidates.append(
                    Product(project_id=project_id, name=product.name, metadata={"sku": product.sku})
                )

        def report(product: ScrapedProduct) -> None:
            products.append(product)
            if on_product:
                on_product(product)

        def fail(url: str, exc: Exception) -> None:
            if on_failure:
                on_failure(url, capture_error_message(exc))

        api = getattr(browser, "request", None) if use_api else None
        if api is None:
            queue.extend(normalized_urls)
        else:
            show_api_notice(tabs.free[0])
            refused_in_a_row = 0
            for url in normalized_urls:
                raise_if_stopped()
                if refused_in_a_row >= API_GIVE_UP_AFTER:
                    queue.append(url)
                    continue
                wait_for_api_slot(tabs.free[0])
                try:
                    product = capture_via_api(
                        api, project_id, url, download_cover, download_model,
                        sku_candidates=sku_candidates, project=project, store_profile=store_profile,
                    )
                except CollectStopped:
                    raise
                except MakerWorldModelMissing as exc:
                    # The API answered; only this link is gone.
                    refused_in_a_row = 0
                    fail(url, exc)
                    continue
                except Exception as exc:
                    refused_in_a_row += 1
                    queue.append(url)
                    if on_log:
                        on_log(f"API do MakerWorld não atendeu {url} ({capture_error_message(exc)}); será lido pela página.")
                        if refused_in_a_row == API_GIVE_UP_AFTER:
                            on_log("A API recusou vários links seguidos; os demais serão lidos pelas páginas.")
                    continue
                refused_in_a_row = 0
                remember_sku(product)
                report(product)
            if on_log and products:
                on_log(f"{len(products)} produto(s) lido(s) pela API do MakerWorld, sem abrir a página.")

        def start_loading() -> None:
            while queue and tabs.busy < tabs.limit:
                page = tabs.take_tab()
                if page is None:
                    return
                url = queue.popleft()
                wait_for_page_slot(page)
                try:
                    # Only wait for the response: the page finishes loading while other tabs work.
                    page.goto(url, wait_until="commit" if tabs.limit > 1 else "domcontentloaded", timeout=60_000)
                except CollectStopped:
                    raise
                except Exception as exc:
                    tabs.release(page)
                    fail(url, exc)
                    continue
                tabs.loading.append(_LoadingPage(url, page, time.monotonic()))
                tabs.mark(page, "loading")

        def finish_download(item: _PendingDownload) -> None:
            product = item.product
            try:
                product.model_file_path = save_3mf_download(
                    item.download, product_assets_dir(project_id, product.sku), product.sku,
                )
            except Exception as exc:
                product.model_error = f"{exc.__class__.__name__}: {exc}"
            tabs.release(item.page)
            report(product)

        def capture(item: _LoadingPage) -> None:
            page, url = item.page, item.url
            tabs.focus(page)
            try:
                if tabs.cleared_at > item.started_at and is_cloudflare_challenge(page):
                    # Loaded before the user solved a check in another tab: the clearance applies now.
                    page.reload(wait_until="commit", timeout=60_000)
                title = wait_with_help(page, lambda: model_page_title(page), notify)
                if not title:
                    raise RuntimeError("a página do modelo não carregou (verificação não resolvida ou tempo esgotado)")
                product = scrape_current_product_page(
                    project_id,
                    page,
                    url,
                    download_cover,
                    sku_candidates=sku_candidates,
                    project=project,
                    store_profile=store_profile,
                    title=title,
                )
            except CollectStopped:
                raise
            except Exception as exc:
                tabs.release(page)
                fail(url, exc)
                return
            # Reported only after its download; the next page must not reuse this SKU meanwhile.
            remember_sku(product)
            if not (download_model and product.sku):
                tabs.release(page)
                report(product)
                return
            product_assets_dir(project_id, product.sku).mkdir(parents=True, exist_ok=True)
            try:
                download = start_3mf_download(page, on_attention=notify)
            except CollectStopped:
                # Its photos are already on disk: keep it, like a download that timed out.
                product.model_error = "download interrompido: coleta parada pelo usuário"
                report(product)
                raise
            except Exception as exc:
                product.model_error = f"{exc.__class__.__name__}: {exc}"
                tabs.release(page)
                report(product)
                return
            # The tab keeps the download until it is saved; the next page loads in another tab.
            tabs.pending.append(_PendingDownload(product, download, page))
            tabs.mark(page, "downloading")

        try:
            while queue or tabs.loading or tabs.pending:
                raise_if_stopped()
                start_loading()
                # Save the oldest download when its tab is needed or nothing else is left to do.
                if tabs.pending and (not tabs.loading or (queue and len(tabs.pending) >= 2)):
                    finish_download(tabs.pending.popleft())
                    continue
                if tabs.loading:
                    capture(tabs.loading.popleft())
        except CollectStopped:
            # Pages already read keep their photos and text, without the 3D file.
            while tabs.pending:
                item = tabs.pending.popleft()
                item.product.model_error = "download interrompido: coleta parada pelo usuário"
                report(item.product)
            raise

    return products


def capture_error_message(exc: Exception) -> str:
    if isinstance(exc, PlaywrightTimeoutError):
        return "tempo esgotado ao abrir a página"
    lines = str(exc).strip().splitlines()
    return (lines[0] if lines else exc.__class__.__name__)[:300]


def scrape_current_product_page(
    project_id: str,
    page,
    url: str,
    download_cover: bool,
    sku_candidates: list[Product] | None = None,
    project: Project | None = None,
    store_profile: StoreProfile | None = None,
    title: str | None = None,
) -> ScrapedProduct:
    title = title or model_page_title(page) or url.rstrip("/").split("/")[-1].replace("-", " ").title()

    description = ""
    for selector in ("meta[property='og:description']", "meta[name='description']"):
        element = page.query_selector(selector)
        if element:
            description = (element.get_attribute("content") or "").strip()
            if description:
                break

    image_url = None
    image_meta = page.query_selector("meta[property='og:image']")
    if image_meta:
        image_url = image_meta.get_attribute("content")

    tags = page.eval_on_selector_all(
        "a[href*='/tags/']",
        "elements => [...new Set(elements.map(element => element.textContent.trim()).filter(Boolean))]",
    )

    sku = None
    if sku_candidates is not None and project and store_profile:
        sku = resolve_sku_for_capture(title, sku_candidates, project, store_profile)

    local_image_path = None
    if download_cover and image_url and sku:
        local_image_path = download_cover_image(project_id, sku, image_url)

    return ScrapedProduct(
        name=title,
        source_url=url,
        tags=tags if isinstance(tags, list) else [],
        description=description,
        image_url=image_url,
        local_image_path=local_image_path,
        sku=sku,
    )


def download_cover_image(project_id: str, sku: str, image_url: str) -> str | None:
    try:
        output_path = download_cover_file(project_id, sku, image_url)
        return str(output_path)
    except Exception:
        return None


def download_approved_product_assets(
    project_id: str,
    product_url: str,
    title: str,
    image_url: str | None,
    sku: str,
    headless: bool = False,
    store_profile: StoreProfile | None = None,
) -> DownloadedProductAssets:
    headless = False
    assets = DownloadedProductAssets()
    if image_url:
        assets.cover_image_path = download_cover_image(project_id, sku, image_url)

    with sync_playwright() as playwright, ExitStack() as contexts:
        browser = contexts.enter_context(open_makerworld_context(
            playwright,
            headless=headless,
            store_profile_id=store_profile.id if store_profile else None,
        ))
        page = browser.new_page()
        try:
            page.goto(product_url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)
            if "Just a moment" in (page.title() or ""):
                if headless:
                    raise RuntimeError("MakerWorld bloqueou navegador headless com Cloudflare.")
                page.wait_for_timeout(20_000)

            product_dir = product_assets_dir(project_id, sku)
            product_dir.mkdir(parents=True, exist_ok=True)
            assets.model_file_path = download_3mf_from_current_page(page, product_dir, sku)
        except Exception as exc:
            assets.model_error = f"{exc.__class__.__name__}: {exc}"
        finally:
            browser.close()

    return assets


def download_3mf_from_current_page(
    page,
    product_dir: Path,
    sku: str,
    on_attention: AttentionCallback | None = None,
) -> str | None:
    return save_3mf_download(start_3mf_download(page, on_attention), product_dir, sku)


def start_3mf_download(page, on_attention: AttentionCallback | None = None):
    """Click the page's 3MF download and return it once the browser has started it."""
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(3500)
    dismiss_cookie_banner(page)
    return download_from_studio_menu(page, on_attention) or download_from_legacy_buttons(page)


def save_3mf_download(download, product_dir: Path, sku: str) -> str:
    """Wait for a started download to finish and keep it under the product's SKU."""
    product_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(download.suggested_filename).suffix or ".3mf"
    output_path = product_dir / model_filename(sku, suffix)
    download.save_as(str(output_path))
    return str(output_path)


def dismiss_cookie_banner(page) -> None:
    """The TrustArc banner covers the download button; rejecting optional cookies closes it."""
    button = page.locator(".trustarc-banner-wrapper").get_by_role("button", name=REJECT_COOKIES_TEXT)
    try:
        if button.count() and button.first.is_visible():
            button.first.click(timeout=3_000)
            page.wait_for_timeout(500)
    except PlaywrightError:
        pass


def download_from_studio_menu(page, on_attention: AttentionCallback | None = None):
    """Current layout: a green split button in the print-files panel.

    Its main action is "Open in Bambu Studio" (which opens an import dialog, not a download) or,
    after an account has downloaded before, "Download 3MF". The other actions sit behind its arrow.
    """
    main = page.locator("span.primaryButton")
    try:
        target = main.filter(has_text=DOWNLOAD_3MF_TEXT).last
        if not target.count():
            arrow = main.filter(has_text=STUDIO_BUTTON_TEXT).locator(
                "xpath=following-sibling::*[contains(@class, 'icon-box')]"
            ).last
            if not arrow.count():
                return None
            # Centered, the arrow is clear of the cookie banner and the floating "TOP" button.
            arrow.evaluate("element => element.scrollIntoView({block: 'center'})")
            arrow.click(timeout=5_000)
            target = page.get_by_text(DOWNLOAD_3MF_TEXT).last
            target.wait_for(state="visible", timeout=5_000)
        else:
            target.evaluate("element => element.scrollIntoView({block: 'center'})")
    except PlaywrightError:
        return None

    downloads = []
    handler = lambda download: downloads.append(download)
    page.on("download", handler)
    try:
        target.click(timeout=5_000)
        # A MakerWorld puzzle can hold the download until someone solves it in the panel.
        download = wait_with_help(page, lambda: downloads[0] if downloads else None, on_attention, ask_after_seconds=8, attention_note=DOWNLOAD_WAIT_NOTE)
    finally:
        page.remove_listener("download", handler)
    if download is None:
        raise RuntimeError("O download do 3MF não começou (verificação não resolvida ou tempo esgotado).")
    return download


def download_from_legacy_buttons(page):
    option_patterns = [
        r"Baixar 3MF",
        r"Download 3MF",
        r"3MF",
        r"Baixar STL",
        r"Download STL",
    ]
    main_button = wait_for_download_entrypoint(page, option_patterns, timeout_ms=35_000)

    if not main_button:
        raise RuntimeError(f"Botao de download/abrir Bambu nao encontrado. Botoes visiveis: {visible_button_sample(page)}")

    if main_button == "direct-option":
        downloaded = click_visible_download_option(page, option_patterns)
    else:
        downloaded = try_click_download_option(page, main_button, option_patterns)
    if not downloaded:
        raise RuntimeError(f"Opcao Baixar 3MF nao apareceu no menu. Botoes visiveis: {visible_button_sample(page)}")
    return downloaded.value


def wait_for_download_entrypoint(page, option_patterns: list[str], timeout_ms: int = 30_000):
    deadline = time.monotonic() + (timeout_ms / 1000)
    first_iteration = True
    while first_iteration or time.monotonic() < deadline:
        raise_if_stopped()
        first_iteration = False
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        if find_download_option(page, option_patterns):
            return "direct-option"

        main_button = find_visible_locator(
            page,
            [
                page.locator(
                    "button",
                    has_text=re.compile(r"Abrir no Bambu Studio|Aberto no Bambu Studio|Open in Bambu Studio", re.IGNORECASE),
                ).first,
                page.locator("button", has_text=re.compile(r"Baixar|Download", re.IGNORECASE)).first,
                page.get_by_text(
                    re.compile(r"Abrir no Bambu Studio|Aberto no Bambu Studio|Open in Bambu Studio", re.IGNORECASE)
                ).last,
                page.get_by_text(re.compile(r"Baixar modelo|Download model|Download files|Baixar arquivos", re.IGNORECASE)).last,
            ],
            timeout=1200,
        )
        if main_button:
            return main_button

        try:
            page.mouse.wheel(0, 500)
            page.wait_for_timeout(700)
            page.mouse.wheel(0, -500)
        except Exception:
            pass
        page.wait_for_timeout(2200)
    return None


def find_visible_locator(page, locators, timeout: int = 3000):
    for locator in locators:
        try:
            if locator.is_visible(timeout=timeout):
                return locator
        except Exception:
            continue
    return None


def click_visible_download_option(page, option_patterns: list[str]):
    option = find_download_option(page, option_patterns)
    if not option:
        return None
    try:
        with page.expect_download(timeout=60_000) as download_info:
            option.click(force=True)
        return download_info
    except Exception:
        return None


def try_click_download_option(page, main_button, option_patterns: list[str]):
    click_targets = [main_button]
    try:
        box = main_button.bounding_box()
        if box:
            click_targets.append(("coords", box["x"] + box["width"] + 15, box["y"] + box["height"] / 2))
            click_targets.append(("coords", box["x"] + box["width"] - 8, box["y"] + box["height"] / 2))
    except Exception:
        pass

    for target in click_targets:
        try:
            try:
                with page.expect_download(timeout=1800) as direct_download:
                    if isinstance(target, tuple):
                        page.mouse.click(target[1], target[2])
                    else:
                        target.click(force=True)
                return direct_download
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(1200)

            option = find_download_option(page, option_patterns)
            if option:
                with page.expect_download(timeout=60_000) as download_info:
                    option.click(force=True)
                return download_info
        except Exception:
            continue
    return None


def find_download_option(page, patterns: list[str]):
    containers = [
        "div[role='tooltip']",
        "div[role='menu']",
        "[class*='popover']",
        "[class*='dropdown']",
        "body",
    ]
    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        for container in containers:
            locator = page.locator(container).get_by_text(regex).last
            try:
                if locator.is_visible(timeout=1000):
                    return locator
            except Exception:
                continue
    return None


def visible_button_sample(page) -> str:
    try:
        buttons = page.locator("button").evaluate_all(
            """buttons => buttons
                .filter(button => {
                    const style = window.getComputedStyle(button);
                    const rect = button.getBoundingClientRect();
                    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
                })
                .slice(0, 12)
                .map(button => (button.innerText || button.getAttribute('aria-label') || button.title || '').trim())
                .filter(Boolean)
            """
        )
        return " | ".join(buttons)[:500] or "nenhum texto de botao visivel"
    except Exception:
        return "nao foi possivel listar botoes"
