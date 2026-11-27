from contextlib import contextmanager
import json
from pathlib import Path

from backend.app.db.models import Project, StoreProfile
from backend.app.services import makerworld_scraper as scraper
from backend.app.services.makerworld_scraper import ScrapedProduct

API = "https://makerworld.com/api/v1/design-service"


class Response:
    def __init__(self, status=200, data=None, body=b"", content_type="application/json"):
        self.status = status
        self.ok = 200 <= status < 300
        self.headers = {"content-type": content_type}
        self._data = data
        self._body = body

    def json(self):
        return self._data

    def body(self):
        return self._body


def design(design_id, title, instances=(("10", "0.2mm"),), default="10"):
    return {
        "id": design_id,
        "title": title,
        "summary": "<p>Um suporte&nbsp;simples.</p><p>Imprime sem suportes.</p>",
        "tags": ["casa", " organizador "],
        "coverUrl": f"https://makerworld.bblmw.com/cover-{design_id}.jpg",
        "defaultInstanceId": default,
        "instances": [{"id": i, "title": t} for i, t in instances],
    }


class Api:
    """MakerWorld's routes; `blocked` design ids answer with Cloudflare's HTML page."""

    def __init__(self, designs, blocked=()):
        self.designs = designs
        self.blocked = set(blocked)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if url.startswith(f"{API}/design/"):
            design_id = url.rsplit("/", 1)[1]
            if design_id in self.blocked:
                return Response(403, body=b"<html>Just a moment...</html>", content_type="text/html")
            if design_id not in self.designs:
                return Response(404, {"code": 404, "error": "The server cannot find the requested resource."})
            return Response(data=self.designs[design_id])
        if url.startswith(f"{API}/instance/"):
            instance = url.split("/instance/")[1].split("/")[0]
            return Response(data={"name": "Model v1.3mf", "url": f"https://makerworld.bblmw.com/file-{instance}.3mf?exp=1"})
        if url.startswith("https://makerworld.bblmw.com/file-"):
            return Response(body=b"PK\x03\x04fake-3mf", content_type="application/octet-stream")
        raise AssertionError(url)


class Tab:
    def __init__(self, log):
        self.log = log
        self.url = ""

    def goto(self, url, **kwargs):
        self.url = url
        self.log.append(url)

    def evaluate(self, script):
        return {"challenge": False, "heading": "Pela página", "og_title": ""}

    def wait_for_timeout(self, milliseconds):
        pass


def run(monkeypatch, tmp_path, urls, api, failures=None):
    pages_opened = []
    browser = type("Browser", (), {})()
    browser.pages = [Tab(pages_opened)]
    browser.request = api

    @contextmanager
    def fake_context(*args, **kwargs):
        yield browser

    @contextmanager
    def fake_playwright():
        yield object()

    monkeypatch.setattr(scraper, "sync_playwright", fake_playwright)
    monkeypatch.setattr(scraper, "open_makerworld_context", fake_context)
    monkeypatch.setattr(scraper, "product_assets_dir", lambda project_id, sku: tmp_path / sku)
    monkeypatch.setattr(scraper, "download_cover_image", lambda project_id, sku, url: f"cover-{sku}.jpg")
    monkeypatch.setattr(scraper, "resolve_sku_for_capture",
                        lambda title, candidates, project, store: f"SKU-{len(candidates) + 1}")
    monkeypatch.setattr(scraper, "scrape_current_product_page", lambda project_id, page, url, *args, **kwargs:
        ScrapedProduct(name=kwargs["title"], source_url=url))
    saved, logs = [], []
    scraper.scrape_product_urls(
        "project", urls, download_model=True, sku_reference_products=[], project=Project(name="P"),
        store_profile=StoreProfile(id="shop", name="Loja"), on_product=saved.append, on_log=logs.append,
        on_failure=lambda url, reason: (failures if failures is not None else []).append((url, reason)),
        use_api=True,
    )
    return saved, logs, pages_opened


def test_models_come_through_the_api_without_opening_their_pages(monkeypatch, tmp_path):
    api = Api({"1": design(1, "Suporte"), "2": design(2, "Gancho", instances=(("20", "a"), ("21", "b")), default="21")})
    urls = ["https://makerworld.com/pt/models/1-suporte", "https://makerworld.com/pt/models/2-gancho"]
    saved, logs, pages_opened = run(monkeypatch, tmp_path, urls, api)

    assert pages_opened == []
    assert [p.name for p in saved] == ["Suporte", "Gancho"]
    first = saved[0]
    assert first.sku == "SKU-1" and saved[1].sku == "SKU-2"  # each model sees the SKU before it
    assert first.description == "Um suporte simples.\nImprime sem suportes."
    assert first.tags == ["casa", "organizador"]
    assert first.image_url == "https://makerworld.bblmw.com/cover-1.jpg"
    assert first.local_image_path == "cover-SKU-1.jpg"
    assert Path(first.model_file_path).read_bytes().startswith(b"PK")
    assert first.model_file_path.endswith(".3mf")
    assert f"{API}/instance/21/f3mf?type=download&fileType=" in api.calls  # the model's default profile
    assert "2 produto(s) lido(s) pela API do MakerWorld, sem abrir a página." in logs


def test_profile_in_the_link_picks_that_print_profile(monkeypatch, tmp_path):
    api = Api({"5": design(5, "Vaso", instances=(("50", "a"), ("51", "b")), default="50")})
    run(monkeypatch, tmp_path, ["https://makerworld.com/en/models/5-vaso#profileId-51"], api)
    assert f"{API}/instance/51/f3mf?type=download&fileType=" in api.calls


def test_a_model_the_api_refuses_is_read_from_its_page(monkeypatch, tmp_path):
    api = Api({"2": design(2, "Gancho")}, blocked={"1"})
    urls = ["https://makerworld.com/pt/models/1", "https://makerworld.com/pt/models/2"]
    saved, logs, pages_opened = run(monkeypatch, tmp_path, urls, api)

    assert pages_opened == ["https://makerworld.com/pt/models/1"]
    assert {p.source_url: p.name for p in saved} == {
        "https://makerworld.com/pt/models/2": "Gancho",
        "https://makerworld.com/pt/models/1": "Pela página",
    }
    assert any("não atendeu https://makerworld.com/pt/models/1" in line and "Cloudflare" in line for line in logs)


def test_after_several_refusals_the_rest_go_straight_to_their_pages(monkeypatch, tmp_path):
    urls = [f"https://makerworld.com/pt/models/{n}" for n in range(1, 6)]
    api = Api({}, blocked={str(n) for n in range(1, 6)})
    saved, logs, pages_opened = run(monkeypatch, tmp_path, urls, api)

    assert len([c for c in api.calls if "/design/" in c]) == scraper.API_GIVE_UP_AFTER
    assert pages_opened == urls
    assert len(saved) == 5
    assert "A API recusou vários links seguidos; os demais serão lidos pelas páginas." in logs


def test_a_missing_model_or_a_bad_file_falls_back():
    class BadFile(Api):
        def get(self, url, headers=None, timeout=None):
            if url.startswith("https://makerworld.bblmw.com/"):
                self.calls.append(url)
                return Response(403, body=b"<Error>expired</Error>", content_type="application/xml")
            return super().get(url, headers, timeout)

    for api, url, reason in (
        (BadFile({"3": design(3, "X")}), "https://makerworld.com/pt/models/3", "download do 3MF falhou"),
    ):
        try:
            scraper.capture_via_api(api, "p", url, False, True, sku_candidates=[], project=Project(name="P"),
                                    store_profile=StoreProfile(id="s", name="L"))
        except scraper.MakerWorldApiUnavailable as exc:
            assert reason in str(exc)
        else:
            raise AssertionError("expected MakerWorldApiUnavailable")


def test_html_summary_becomes_plain_text():
    assert scraper.html_to_text("<h2>Título</h2><p>Linha&amp;1<br/>Linha 2</p><ul><li>a</li></ul>") == (
        "Título\nLinha&1\nLinha 2\na"
    )
    assert json.dumps(scraper.html_to_text("")) == '""'


def test_a_model_that_no_longer_exists_fails_without_opening_its_page(monkeypatch, tmp_path):
    failures = []
    api = Api({"2": design(2, "Gancho")})
    urls = ["https://makerworld.com/pt/models/9", "https://makerworld.com/pt/models/2"]
    saved, logs, pages_opened = run(monkeypatch, tmp_path, urls, api, failures)

    assert pages_opened == []
    assert [p.name for p in saved] == ["Gancho"]
    assert failures == [("https://makerworld.com/pt/models/9", "o modelo não existe mais no MakerWorld")]
