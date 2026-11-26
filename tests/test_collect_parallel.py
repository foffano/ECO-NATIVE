from contextlib import contextmanager
from types import SimpleNamespace

from backend.app.db.models import Job, Project, StoreProfile
from backend.app.db.store import store
from backend.app.services import job_runner, makerworld_scraper as scraper
from backend.app.services.cdp_viewer import CdpPage
from backend.app.services.makerworld_scraper import ScrapedProduct
from backend.app.services.rate_limiter import RateLimiter

URLS = [f"https://makerworld.com/pt/models/{n}" for n in range(1, 5)]


class Tab:
    def __init__(self, log):
        self.log = log
        self.url = ""

    def goto(self, url, **kwargs):
        self.url = url
        self.log.append(("goto", url[-1]))

    def evaluate(self, script):
        return {"challenge": False, "heading": f"Modelo {self.url[-1]}", "og_title": ""}

    def wait_for_timeout(self, milliseconds):
        pass


class Download:
    suggested_filename = "x.3mf"

    def __init__(self, log, name):
        self.log, self.name = log, name

    def save_as(self, path):
        self.log.append(("save", self.name))


class Browser:
    def __init__(self, log):
        self.log = log
        self.pages = [Tab(log)]

    def new_page(self):
        self.pages.append(Tab(self.log))
        return self.pages[-1]


def run_scrape(monkeypatch, tmp_path, parallel, urls=URLS):
    log = []
    browser = Browser(log)

    @contextmanager
    def fake_context(*args, **kwargs):
        yield browser

    @contextmanager
    def fake_playwright():
        yield object()

    monkeypatch.setattr(scraper, "sync_playwright", fake_playwright)
    monkeypatch.setattr(scraper, "open_makerworld_context", fake_context)
    monkeypatch.setattr(scraper, "product_assets_dir", lambda project_id, sku: tmp_path / sku)
    monkeypatch.setattr(scraper, "start_3mf_download", lambda page, **kwargs: Download(log, page.url[-1]))
    monkeypatch.setattr(scraper, "scrape_current_product_page", lambda project_id, page, url, *args, **kwargs:
        ScrapedProduct(name=kwargs["title"], source_url=url, sku=f"SKU-{url[-1]}"))
    saved = []
    scraper.scrape_product_urls("project", urls, download_model=True, on_product=saved.append, parallel=parallel)
    return log, browser, saved


def test_next_page_loads_while_the_previous_download_runs(monkeypatch, tmp_path):
    log, browser, saved = run_scrape(monkeypatch, tmp_path, parallel=2)

    assert log == [
        ("goto", "1"), ("goto", "2"), ("save", "1"),
        ("goto", "3"), ("save", "2"),
        ("goto", "4"), ("save", "3"), ("save", "4"),
    ]
    assert len(browser.pages) == 2  # never more tabs than the limit
    assert [p.source_url for p in saved] == URLS
    assert all(p.model_file_path and p.model_file_path.endswith(".3mf") for p in saved)


def test_one_page_at_a_time_keeps_the_old_sequential_order(monkeypatch, tmp_path):
    log, browser, saved = run_scrape(monkeypatch, tmp_path, parallel=1)

    assert log == [("goto", "1"), ("save", "1"), ("goto", "2"), ("save", "2"),
                   ("goto", "3"), ("save", "3"), ("goto", "4"), ("save", "4")]
    assert len(browser.pages) == 1
    assert len(saved) == 4


def test_parallel_limit_is_clamped(monkeypatch):
    monkeypatch.setattr(scraper, "MAX_COLLECT_PARALLEL", 4)
    assert scraper.collect_parallelism(None) == scraper.DEFAULT_COLLECT_PARALLEL == 2
    assert scraper.collect_parallelism(0) == 1
    assert scraper.collect_parallelism(9) == 4


def test_a_check_slows_the_collect_and_marks_when_it_was_solved():
    logs, notices = [], []
    tabs = scraper._CollectTabs(Browser([]), 3, None, logs.append)
    notify = tabs.attention(notices.append)

    notify(scraper.VERIFICATION_PROMPT)
    notify(scraper.VERIFICATION_PROMPT)  # same check, counted once
    assert tabs.limit == 2 and tabs.cleared_at == 0
    assert logs == ["O MakerWorld pediu verificação; a coleta segue com 2 página(s) por vez."]
    notify(None)
    assert tabs.cleared_at > 0
    assert notices == [scraper.VERIFICATION_PROMPT, scraper.VERIFICATION_PROMPT, None]


def test_tab_loaded_before_a_solved_check_is_reloaded(monkeypatch, tmp_path):
    """Other tabs that hit the same Cloudflare page pass once the user solved it in one."""
    log = []
    browser = Browser(log)
    reloads = []

    class ChallengedTab(Tab):
        challenged = True

        def evaluate(self, script):
            if "_cf_chl_opt" in script and "heading" not in script:
                return self.challenged
            return {"challenge": self.challenged, "heading": "" if self.challenged else "Modelo", "og_title": ""}

        def reload(self, **kwargs):
            reloads.append(self.url)
            self.challenged = False

    browser.pages = [ChallengedTab(log)]
    browser.new_page = lambda: browser.pages.append(ChallengedTab(log)) or browser.pages[-1]

    @contextmanager
    def fake_context(*args, **kwargs):
        yield browser

    @contextmanager
    def fake_playwright():
        yield object()

    first_tab = browser.pages[0]
    polls = {"n": 0}
    real_wait = scraper.wait_with_help

    def solving_wait(page, ready, on_attention=None, **kwargs):
        if page is first_tab and page.challenged:
            on_attention(scraper.VERIFICATION_PROMPT)
            page.challenged = False  # the user solved it in the panel
            on_attention(None)
        polls["n"] += 1
        return real_wait(page, ready, on_attention, **kwargs)

    monkeypatch.setattr(scraper, "sync_playwright", fake_playwright)
    monkeypatch.setattr(scraper, "open_makerworld_context", fake_context)
    monkeypatch.setattr(scraper, "wait_with_help", solving_wait)
    monkeypatch.setattr(scraper, "scrape_current_product_page", lambda project_id, page, url, *args, **kwargs:
        ScrapedProduct(name=kwargs["title"], source_url=url))
    saved = []
    scraper.scrape_product_urls("project", URLS[:2], on_product=saved.append, parallel=2)

    assert reloads == [URLS[1]]
    assert len(saved) == 2


class ClockPage:
    """Each poll takes 50 s; a check stays on screen for the first `checks` polls."""

    def __init__(self, clock, checks):
        self.clock, self.checks = clock, checks

    def evaluate(self, script):
        return self.checks > 0

    def wait_for_timeout(self, milliseconds):
        self.clock["now"] += 50
        self.checks -= 1


def test_a_check_on_screen_pauses_the_timeout_until_solved(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(scraper.time, "monotonic", lambda: clock["now"])
    page = ClockPage(clock, checks=8)  # 400 s on screen, longer than the 180 s timeout
    notices = []
    value = scraper.wait_with_help(page, lambda: "ok" if page.checks <= 0 else None, notices.append)
    assert value == "ok"
    assert notices == [scraper.VERIFICATION_PROMPT, None]

    clock["now"] = 0.0
    stuck = ClockPage(clock, checks=10**6)
    assert scraper.wait_with_help(stuck, lambda: None, None, max_pause_seconds=600) is None
    assert 600 <= clock["now"] <= 700


def test_page_loads_wait_for_the_shared_pace(monkeypatch):
    clock = {"now": 0.0}
    limiter = RateLimiter(2, 60.0)
    monkeypatch.setattr(scraper.rate_limiter, "makerworld_page_limiter", limiter)
    monkeypatch.setattr("backend.app.services.rate_limiter.time.monotonic", lambda: clock["now"])
    waits = []

    class Waiting:
        def wait_for_timeout(self, milliseconds):
            waits.append(milliseconds)
            clock["now"] += milliseconds / 1000

    for _ in range(3):
        scraper.wait_for_page_slot(Waiting())
    # The third load waits for the window, in short slices so a stop is noticed.
    assert waits and max(waits) <= 1000
    assert clock["now"] >= 60


def test_collect_job_pauses_for_a_check_and_passes_the_limit(monkeypatch):
    shop = store.upsert_store_profile(StoreProfile(name="Loja"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    seen = {}

    def fake_scrape(**kwargs):
        seen["parallel"] = kwargs["parallel"]
        kwargs["on_attention"](scraper.VERIFICATION_PROMPT)
        job = store.load().jobs[0]
        seen["paused"] = job.metadata.get("paused_for_verification")
        seen["attention"] = job.metadata.get("attention")
        kwargs["on_attention"](None)
        kwargs["on_log"]("linha do scraper")
        kwargs["on_product"](ScrapedProduct(name="A", source_url=URLS[0], sku="LOJA-A-0001"))
        return []

    monkeypatch.setattr(job_runner, "scrape_product_urls", fake_scrape)
    job = store.upsert_job(Job(type="collect_products", project_id=project.id))
    payload = SimpleNamespace(project_id=project.id, store_profile_id=shop.id, keyword="", urls=URLS[:2],
                              limit=2, scrolls=1, visible_browser=True, parallel=3)
    result = job_runner.run_collect_job(job, payload)

    assert seen == {"parallel": 3, "paused": True, "attention": scraper.VERIFICATION_PROMPT}
    assert "paused_for_verification" not in result.metadata
    assert "Coleta pausada: o MakerWorld pediu verificação." in result.logs
    assert "Verificação resolvida; a coleta continua." in result.logs
    assert "linha do scraper" in result.logs
    assert "Até 3 página(s) de produto por vez." in result.logs


def test_viewer_follows_the_job_to_another_tab_and_keeps_its_sessions():
    page = CdpPage.__new__(CdpPage)
    page._session, page._target, page._attached = "session-1", "tab-1", {"tab-1": "session-1"}
    calls = []

    def call(method, params=None, page=True, **kwargs):
        calls.append((method, params))
        if method == "Target.getTargets":
            return {"targetInfos": [
                {"targetId": "tab-1", "type": "page", "url": "https://makerworld.com/pt/models/1"},
                {"targetId": "tab-2", "type": "page", "url": "https://makerworld.com/pt/models/2"},
            ]}
        if method == "Target.attachToTarget":
            return {"sessionId": "session-2"}
        return {}

    page.call = call
    page.switch_to("tab-2")
    assert (page.target_id, page._session) == ("tab-2", "session-2")
    calls.clear()
    page.switch_to("tab-2")
    assert calls == []
    # Back to the first page: its session (also used for its preview) is reused.
    page.switch_to("tab-1")
    assert page._session == "session-1"
    assert [method for method, _ in calls] == ["Target.getTargets"]


class WindowBrowser(Browser):
    """Opens new windows through DevTools, like the real collect browser."""

    def __init__(self, log):
        super().__init__(log)
        self.created_windows = []
        self._opened = None

    def new_cdp_session(self, page):
        browser = self

        class Session:
            def send(self, method, params=None):
                if method == "Target.createTarget":
                    browser.created_windows.append(params)
                    browser._opened = Tab(browser.log)
                    browser.pages.append(browser._opened)
                    return {"targetId": "new"}
                return {"targetInfo": {"targetId": f"target-{browser.pages.index(page) + 1}"}}

            def detach(self):
                pass

        return Session()

    @contextmanager
    def expect_page(self, timeout=None):
        holder = SimpleNamespace()
        yield holder
        holder.value = self._opened


def test_extra_pages_open_in_their_own_windows_and_report_their_state(monkeypatch):
    from backend.app.services import makerworld_session

    published = []
    monkeypatch.setattr(makerworld_session, "set_collect_tabs", lambda store, tabs: published.append(tabs))
    monkeypatch.setattr(makerworld_session, "set_collect_target", lambda store, target: published.append(target))
    browser = WindowBrowser([])
    tabs = scraper._CollectTabs(browser, 2, "shop", None)
    first = tabs.take_tab()
    tabs.mark(first, "loading")
    assert published == []  # one page: nothing to preview
    second = tabs.take_tab()
    assert browser.created_windows == [{"url": "about:blank", "newWindow": True}]
    tabs.mark(second, "loading")
    tabs.focus(first)
    assert published[-2:] == [
        [{"id": "target-1", "state": "reading"}, {"id": "target-2", "state": "loading"}],
        "target-1",
    ]
    tabs.attention(None)(scraper.VERIFICATION_PROMPT)
    assert published[-1] == [{"id": "target-1", "state": "verification"}, {"id": "target-2", "state": "loading"}]
    tabs.release(second)
    assert published[-1][1] == {"id": "target-2", "state": "idle"}


class FakeCdp:
    def __init__(self, endpoint, target_id=None):
        self.target_id = target_id or "t1"
        self.switches = []
        self.previews = []
        self.fail_preview = set()

    def screenshot(self):
        return b"frame-" + self.target_id.encode()

    def evaluate(self, expression):
        return [False, "complete"]

    @property
    def url(self):
        return f"https://makerworld.com/pt/models/{self.target_id}"

    def tabs(self):
        return [{"targetId": t, "url": f"https://makerworld.com/pt/models/{t}"} for t in ("t1", "t2")]

    def switch_to(self, target_id):
        self.switches.append(target_id)
        self.target_id = target_id

    def thumbnail(self, target_id, width, height):
        from backend.app.services.cdp_viewer import CdpError
        if target_id in self.fail_preview:
            raise CdpError("sem pintura")
        self.previews.append(target_id)
        return b"preview-" + target_id.encode()

    def evaluate_in(self, target_id, expression):
        return target_id == "t2"

    def close(self):
        pass


def test_collect_viewer_shows_previews_and_lets_the_user_pick_a_page(monkeypatch):
    import time
    from backend.app.services import makerworld_session as ms

    fake = {}
    monkeypatch.setattr(ms, "CdpPage", lambda endpoint, target_id=None: fake.setdefault("page", FakeCdp(endpoint, target_id)))
    monkeypatch.setattr(ms, "FRAME_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(ms, "PREVIEW_INTERVAL_SECONDS", 0.0)
    ms._collect_targets["shop"] = "t1"
    ms._collect_tabs["shop"] = [{"id": "t1", "state": "reading"}, {"id": "t2", "state": "loading"}]
    viewer = ms.RemoteBrowserSession("shop", attach_endpoint="http://127.0.0.1:1")

    def wait_for(check):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            viewer.frame()
            if check():
                return True
            time.sleep(0.01)
        return False

    try:
        viewer.start()
        assert wait_for(lambda: viewer.preview("t2") == b"preview-t2")
        status = viewer.status()
        assert status.following and status.job_page_id == "t1" and status.active_page_id == "t1"
        # t2 shows a Cloudflare check in the background: flagged before the collect gets to it.
        assert {p["id"]: p["state"] for p in status.pages} == {"t1": "reading", "t2": "verification"}

        viewer.send({"type": "select_page", "page_id": "t2"})
        assert wait_for(lambda: viewer.status().active_page_id == "t2")
        assert not viewer.status().following
        assert wait_for(lambda: viewer.frame() == b"frame-t2")

        # The collect asks for help on its own page: the view goes back to it.
        ms._collect_notices["shop"] = scraper.VERIFICATION_PROMPT
        assert wait_for(lambda: viewer.status().active_page_id == "t1")
        assert viewer.status().following
    finally:
        viewer.close()
        viewer._thread.join(timeout=3)
        for registry in (ms._collect_targets, ms._collect_tabs, ms._collect_notices):
            registry.pop("shop", None)
