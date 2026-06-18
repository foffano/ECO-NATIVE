import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from backend.app.core.playwright_env import configure_playwright_browsers, playwright_install_hint

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


def open_makerworld_context(playwright, headless: bool):
    if not configure_playwright_browsers():
        raise RuntimeError(playwright_install_hint())
    user_data_path = DATA_DIR / "browser_data" / "makerworld"
    user_data_path.mkdir(parents=True, exist_ok=True)
    try:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_path,
            headless=headless,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
    except PlaywrightError as error:
        message = str(error)
        if "Executable doesn't exist" in message:
            raise RuntimeError(playwright_install_hint()) from error
        raise


def discover_model_urls(
    keyword: str,
    scrolls: int = 8,
    headless: bool = False,
    max_urls: int = 200,
) -> list[str]:
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

    with sync_playwright() as playwright:
        browser = open_makerworld_context(playwright, headless=headless)
        page = browser.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6000)

        if "Just a moment" in (page.title() or ""):
            if headless:
                browser.close()
                raise RuntimeError("MakerWorld bloqueou navegador headless com Cloudflare. Use navegador visivel.")
            page.wait_for_timeout(20_000)

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
) -> list[ScrapedProduct]:
    normalized_urls = []
    for url in urls:
        clean_url = clean_makerworld_url(url)
        if clean_url and clean_url not in normalized_urls:
            normalized_urls.append(clean_url)

    if not normalized_urls:
        return []

    products: list[ScrapedProduct] = []
    sku_candidates = list(sku_reference_products or [])
    with sync_playwright() as playwright:
        browser = open_makerworld_context(playwright, headless=headless)
        page = browser.new_page()

        for url in normalized_urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(1800)
                if "Just a moment" in (page.title() or ""):
                    if headless:
                        raise RuntimeError("MakerWorld bloqueou navegador headless com Cloudflare.")
                    page.wait_for_timeout(20_000)
                product = scrape_current_product_page(
                    project_id,
                    page,
                    url,
                    download_cover,
                    sku_candidates=sku_candidates,
                    project=project,
                    store_profile=store_profile,
                )
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
                        product.model_file_path = download_3mf_from_current_page(page, product_dir, product.sku)
                    except Exception as exc:
                        product.model_error = f"{exc.__class__.__name__}: {exc}"
                products.append(product)
            except PlaywrightTimeoutError:
                fallback_name = url.rstrip("/").split("/")[-1].replace("-", " ").title()
                products.append(ScrapedProduct(name=fallback_name, source_url=url, tags=["timeout"]))
            except Exception as exc:
                fallback_name = url.rstrip("/").split("/")[-1].replace("-", " ").title()
                products.append(ScrapedProduct(name=fallback_name, source_url=url, tags=[f"erro: {exc.__class__.__name__}"]))

        browser.close()

    return products


def scrape_current_product_page(
    project_id: str,
    page,
    url: str,
    download_cover: bool,
    sku_candidates: list[Product] | None = None,
    project: Project | None = None,
    store_profile: StoreProfile | None = None,
) -> ScrapedProduct:
    title = page.locator("h1").text_content(timeout=5000)
    title = title.strip() if title else url.rstrip("/").split("/")[-1].replace("-", " ").title()

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
) -> DownloadedProductAssets:
    assets = DownloadedProductAssets()
    if image_url:
        assets.cover_image_path = download_cover_image(project_id, sku, image_url)

    with sync_playwright() as playwright:
        browser = open_makerworld_context(playwright, headless=headless)
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


def download_3mf_from_current_page(page, product_dir: Path, sku: str) -> str | None:
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(3500)

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

    download_info = downloaded
    download = download_info.value
    suffix = Path(download.suggested_filename).suffix or ".3mf"
    output_path = product_dir / model_filename(sku, suffix)
    download.save_as(str(output_path))
    return str(output_path)


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
