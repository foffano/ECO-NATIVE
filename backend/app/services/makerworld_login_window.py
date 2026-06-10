import time

from playwright.sync_api import sync_playwright

from backend.app.services.makerworld_scraper import MAKERWORLD_HOME, open_makerworld_context


def main() -> None:
    with sync_playwright() as playwright:
        context = open_makerworld_context(playwright, headless=False)
        page = context.new_page()
        page.goto(MAKERWORLD_HOME, wait_until="domcontentloaded", timeout=60_000)

        while True:
            try:
                if page.is_closed():
                    break
                page.wait_for_timeout(2000)
            except Exception:
                break
            time.sleep(0.2)

        context.close()


if __name__ == "__main__":
    main()
