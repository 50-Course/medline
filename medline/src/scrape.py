# NOTE: THis is a custom scrapping script written for the use of an particular
# website and could not be used for any other despite the great efforts at making
# its interfaces composable.
#
# Simply put, its business logic is targeted for use a peculiar website - the afforementioned
# URL and can work for NO other.

import logging
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, ElementHandle
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError, sync_playwright

logger = logging.getLogger(__name__)

url: str = "https://www.medicalexpo.com/"

USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0"

_headers: dict[str, Any] = {}


def scrape_url(
    url: str,
    headless: bool = False,
    slow_mo: int = 0,
    wait_for_load: int = 3000,
    to_excel: bool = False,
    output_dir: Path | None = None,
    send_notification: bool = False,
) -> None:
    """
    Scrape the content of the URL using playwright
    """
    try:
        with sync_playwright() as p:
            browser: Browser = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            ctx: BrowserContext = browser.new_context(user_agent=USER_AGENT)

            page = ctx.new_page()

            page.goto(url, timeout=5000)

            if wait_for_load > 0:
                page.wait_for_timeout(wait_for_load)

            # TODO: we start performing actions in here
            # perhaps, an entrypoint function
            with page.expect_response(
                lambda response: response.status == 200 and response.url == url
            ):
                entrypoint(page)

                # excel file are stored directly on host system if output dir is not specified
                # TODO: write logic later - Lower priority

            # if send notification is enabled, and scraping is successful - then drop a notification
            # TODO: write logic later - Lower priority

    except (PlaywrightError, TimeoutError) as play_err:
        logger.warning("Error scraping URL: ", str(play_err.message))


def entrypoint(page: Page) -> None:
    """
    Peforms a set of operations taking the page as the input
    """
    # we find the 'Product' dropdowns and scrape its category information recursively for both columns
    page.wait_for_selector("div.sc-19e28ua-1.eZHbVe")
    dropdown_container = page.query_selector("div.sc-19e28ua-1.eZHbVe")

    if dropdown_container:
        logger.info("We got here ..waiting for next steps...")

    # then we go into each product category listing (which is like a module index, a product catalog index) page, within a dropdown and scrape all information
    # keeping the heirachy in-tact

    # then we proceed to go into the respective 'Product' Index Detailed Overview Listing page, all available products per index
    # while sticking keeping heirachy in-place

    # then we finally click each 'Product' itself (which is now like Amazon page), then we scrape peculiar information - Images, product information, merchant information, tags, descriptions, and whatnots


if __name__ == "__main__":
    scrape_url(url, headless=True)
