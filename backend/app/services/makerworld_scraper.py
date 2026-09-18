from collections.abc import Callable
from contextlib import ExitStack, contextmanager
import os
import re
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

# Time the user gets to solve a Cloudflare check or MakerWorld puzzle in the collect browser.
MANUAL_CHECK_SECONDS = 180
VERIFICATION_PROMPT = (
    "O MakerWorld pediu uma verificação. Abra o navegador da coleta e resolva para continuar."
)
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


def build_search_url(keyword: str) -> str:
    keyword = keyword.strip()
    if not keyword:
        return MAKERWORLD_HOME
    encoded = urllib.parse.quote(keyword)
    return f"https://makerworld.com/pt/search/models?keyword={encoded}"


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


def wait_with_help(
    page,
    ready: Callable[[], Any],
    on_attention: AttentionCallback | None = None,
    *,
    timeout_seconds: float = MANUAL_CHECK_SECONDS,
    ask_after_seconds: float = 20.0,
) -> Any:
    """Poll ready() until it returns a value, asking the user for help if a check blocks the page."""
    started = time.monotonic()
    asked = False
    try:
        while True:
            try:
                value = ready()
            except PlaywrightError:
                value = None  # The page is navigating.
            if value:
                return value
            elapsed = time.monotonic() - started
            if elapsed >= timeout_seconds:
                return None
            if on_attention and not asked and (elapsed >= ask_after_seconds or is_cloudflare_challenge(page)):
                on_attention(VERIFICATION_PROMPT)
                asked = True
            page.wait_for_timeout(1000)
    finally:
        if asked and on_attention:
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
) -> list[str]:
    headless = False
    target_url = build_search_url(keyword)
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
        page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6000)

        if not wait_with_help(page, lambda: not is_cloudflare_challenge(page), on_attention):
            raise RuntimeError("A verificação de segurança do MakerWorld não foi resolvida a tempo.")

        # Coleta inicial (antes de rolar) e a cada rolagem, para nao perder
        # itens que a lista virtualizada remove do DOM ao sair da tela.
        harvest(page)
        stagnant_rounds = 0
        for _ in range(max(scrolls, 1)):
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
) -> list[ScrapedProduct]:
    """Capture model pages, reporting each product as soon as its files are on disk.

    A page that never loads is reported through on_failure instead of becoming a product,
    so the link can be collected again later.
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
    with sync_playwright() as playwright, ExitStack() as contexts:
        browser = contexts.enter_context(open_makerworld_context(
            playwright,
            headless=False,
            viewport=viewport,
            store_profile_id=store_profile.id if store_profile else None,
            watch=True,
        ))
        page = first_page(browser)

        for url in normalized_urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                title = wait_with_help(page, lambda: model_page_title(page), on_attention)
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
            except Exception as exc:
                if on_failure:
                    on_failure(url, capture_error_message(exc))
                continue
            if product.sku:
                sku_candidates.append(
                    Product(
                        project_id=project_id,
                        name=product.name,
                        metadata={"sku": product.sku},
                    )
                )
            if download_model and product.sku:
                product_dir = product_assets_dir(project_id, product.sku)
                product_dir.mkdir(parents=True, exist_ok=True)
                try:
                    product.model_file_path = download_3mf_from_current_page(
                        page, product_dir, product.sku, on_attention=on_attention,
                    )
                except Exception as exc:
                    product.model_error = f"{exc.__class__.__name__}: {exc}"
            products.append(product)
            if on_product:
                on_product(product)

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
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(3500)
    dismiss_cookie_banner(page)

    download = download_from_studio_menu(page, on_attention) or download_from_legacy_buttons(page)
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
        download = wait_with_help(page, lambda: downloads[0] if downloads else None, on_attention, ask_after_seconds=8)
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
