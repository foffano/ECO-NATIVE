from contextlib import contextmanager
from types import SimpleNamespace

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from backend.app.db.models import Job, JobStatus, Project, StoreProfile
from backend.app.db.store import store
from backend.app.services import job_runner, makerworld_scraper as scraper
from backend.app.services.makerworld_scraper import ScrapedProduct


def collect_payload(project, urls):
    return SimpleNamespace(
        project_id=project.id,
        store_profile_id=project.store_profile_id,
        keyword="",
        urls=urls,
        limit=len(urls),
        scrolls=1,
        visible_browser=True,
    )


def setup_project():
    shop = store.upsert_store_profile(StoreProfile(name="Loja"))
    return store.upsert_project(Project(name="P", store_profile_id=shop.id))


def test_collect_saves_each_product_and_keeps_failed_links_free(monkeypatch):
    project = setup_project()
    seen_in_store = []

    def fake_scrape(**kwargs):
        kwargs["on_attention"]("Resolva a verificação")
        assert store.load().jobs[0].metadata["attention"] == "Resolva a verificação"
        kwargs["on_attention"](None)
        kwargs["on_product"](ScrapedProduct(name="Soap Holder", source_url="https://makerworld.com/pt/models/1", sku="LOJA-SOAP-0001"))
        seen_in_store.append(len(store.load().products))
        kwargs["on_failure"]("https://makerworld.com/pt/models/2", "tempo esgotado ao abrir a página")
        return []

    monkeypatch.setattr(job_runner, "scrape_product_urls", fake_scrape)
    job = store.upsert_job(Job(type="collect_products", project_id=project.id))
    urls = ["https://makerworld.com/pt/models/1", "https://makerworld.com/pt/models/2"]
    result = job_runner.run_collect_job(job, collect_payload(project, urls))

    assert seen_in_store == [1]  # saved before the batch finished
    assert result.status == JobStatus.completed
    assert "1 link(s) falharam" in result.message
    assert "attention" not in result.metadata
    assert any("models/2" in line and "tempo esgotado" in line for line in result.logs)
    state = store.load()
    assert [product.source_url for product in state.products] == ["https://makerworld.com/pt/models/1"]
    assert not state.blocked_source_urls


def test_collect_reports_failure_when_nothing_was_captured(monkeypatch):
    project = setup_project()

    def fake_scrape(**kwargs):
        kwargs["on_failure"]("https://makerworld.com/pt/models/9", "a página do modelo não carregou")
        return []

    monkeypatch.setattr(job_runner, "scrape_product_urls", fake_scrape)
    job = store.upsert_job(Job(type="collect_products", project_id=project.id))
    result = job_runner.run_collect_job(job, collect_payload(project, ["https://makerworld.com/pt/models/9"]))

    assert result.status == JobStatus.failed
    assert "a página do modelo não carregou" in result.logs[-1]
    assert not store.load().products


def test_interrupted_collect_keeps_products_already_saved(monkeypatch):
    project = setup_project()

    def fake_scrape(**kwargs):
        kwargs["on_product"](ScrapedProduct(name="Kept", source_url="https://makerworld.com/pt/models/3", sku="LOJA-KEPT-0001"))
        raise RuntimeError("navegador fechou")

    monkeypatch.setattr(job_runner, "scrape_product_urls", fake_scrape)
    job = store.upsert_job(Job(type="collect_products", project_id=project.id))
    result = job_runner.run_collect_job(job, collect_payload(project, ["https://makerworld.com/pt/models/3"]))

    assert result.status == JobStatus.failed
    assert [product.name for product in store.load().products] == ["Kept"]


class FakePage:
    def __init__(self, fail_urls):
        self.fail_urls = fail_urls

    def goto(self, url, **kwargs):
        if url in self.fail_urls:
            raise PlaywrightTimeoutError("Timeout 60000ms exceeded")

    def evaluate(self, script):
        return {"challenge": False, "heading": "", "og_title": "Soap Holder - Free 3D Print Model - MakerWorld"}

    def wait_for_timeout(self, milliseconds):
        pass


def test_scrape_reports_failed_pages_instead_of_placeholder_products(monkeypatch, tmp_path):
    page = FakePage({"https://makerworld.com/pt/models/2"})

    @contextmanager
    def fake_context(*args, **kwargs):
        assert kwargs["watch"] is True
        yield SimpleNamespace(pages=[page])

    @contextmanager
    def fake_playwright():
        yield object()

    monkeypatch.setattr(scraper, "sync_playwright", fake_playwright)
    monkeypatch.setattr(scraper, "open_makerworld_context", fake_context)
    monkeypatch.setattr(scraper, "download_3mf_from_current_page", lambda *args, **kwargs: str(tmp_path / "model.3mf"))
    monkeypatch.setattr(
        scraper,
        "scrape_current_product_page",
        lambda project_id, page, url, download_cover, **kwargs: ScrapedProduct(name=kwargs["title"], source_url=url, sku="SKU-1"),
    )
    saved, failed = [], []
    products = scraper.scrape_product_urls(
        "project",
        ["https://makerworld.com/pt/models/1", "https://makerworld.com/pt/models/2"],
        download_model=True,
        on_product=saved.append,
        on_failure=lambda url, reason: failed.append((url, reason)),
    )

    assert [product.name for product in saved] == ["Soap Holder"]
    assert saved[0].model_file_path == str(tmp_path / "model.3mf")
    assert products == saved
    assert failed == [("https://makerworld.com/pt/models/2", "tempo esgotado ao abrir a página")]


class ChallengePage:
    def __init__(self, challenge_polls):
        self.challenge_polls = challenge_polls

    def evaluate(self, script):
        return self.challenge_polls > 0

    def wait_for_timeout(self, milliseconds):
        self.challenge_polls -= 1


def test_wait_with_help_asks_for_help_during_a_check_and_clears_it():
    page = ChallengePage(challenge_polls=2)
    notices = []
    value = scraper.wait_with_help(page, lambda: "ready" if page.challenge_polls <= 0 else None, notices.append)
    assert value == "ready"
    assert notices == [scraper.VERIFICATION_PROMPT, None]

    notices.clear()
    stuck = ChallengePage(challenge_polls=10**6)
    assert scraper.wait_with_help(stuck, lambda: None, notices.append, timeout_seconds=0.05) is None
    assert notices == [scraper.VERIFICATION_PROMPT, None]


def test_model_title_reads_logged_in_layout_and_rejects_cloudflare():
    class StatePage:
        def __init__(self, state):
            self.state = state

        def evaluate(self, script):
            return self.state

    assert scraper.model_page_title(StatePage({"challenge": True, "heading": "makerworld.com", "og_title": ""})) is None
    assert scraper.model_page_title(StatePage({"challenge": False, "heading": "Saboneteira", "og_title": "x"})) == "Saboneteira"
    logged_in = StatePage({"challenge": False, "heading": "", "og_title": "Soap Dish - Modern - Free 3D Print Model - MakerWorld"})
    assert scraper.model_page_title(logged_in) == "Soap Dish - Modern"
    assert scraper.strip_makerworld_title_suffix("Saboneteira - Modelo gratuito para impressão 3D - MakerWorld") == "Saboneteira"
