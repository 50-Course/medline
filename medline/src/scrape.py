# NOTE: THis is a custom scrapping script written for the use of an particular
# website and could not be used for any other despite the great efforts at making
# its interfaces composable.
#
# Simply put, its business logic is targeted for use a peculiar website - the afforementioned
# URL and can work for NO other.

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, NewType, Optional

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Browser, BrowserContext, ElementHandle
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError, sync_playwright

logger = logging.getLogger(__name__)

url: str = "https://www.medicalexpo.com/"

_headers: dict[str, Any] = {}

_BrowserArgs = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--no-zygote",
    "--disable-gpu",
    "--disable-features=IsolateOrigins,site-per-process",  # disable site isolation
    "--window-size=1280,800",
]

_ResponseData = Annotated[
    dict,
    "A Prettified response output beautifully coarsed into JSON for efficient storage and manupulation",
]

USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0"
_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
_VIEWPORT = ({"width": 1280, "height": 800},)


SELECTOR_HOMEPAGE_PRODUCTS_COLUMN: str = "div.sc-19e28ua-1.eZHbVe"
SELECTOR_ROW_CATEGORY: str = (
    "div.row__Row-sc-wfit35-0.universGroup__MenuRow-sc-6qd6g7-6.kVmZTr"
)
SELECTOR_PRODUCT_CATEGORY_COLUMN: str = (
    "div.column__Column-sc-ztyvp1-0.universGroup__MenuColumn-sc-6qd6g7-7.eaYfnt"
)
ATTR_TYPE_SELECTOR_LIST_PRODUCT_CATEGORY: str = (
    "li.universGroup__UniverseGroupItemComponent-sc-6qd6g7-3.dTahsv"
)
ATTR_TYPE_SELECTOR_SPAN_PRODUCT_CATEGORY: str = (
    "span.universGroup__UniverseGroupLabel-sc-6qd6g7-10.gKaSAR"
)
SELECTOR_CONTAINER_HOMEPAGE_PRODUCT_CATEGORY_ITEM: str = (
    "ul.universGroup__CategoryUl-sc-6qd6g7-4.iCVouy"
)
ATTR_TYPE_SELECTOR_HOMEPAGE_PRODUCT_CATEGORY_ITEM: str = (
    "li.universGroup__CategoryLi-sc-6qd6g7-8.yUtRm"
)
SELECTOR_ATTR_A_HOMEPAGE_PRODUCT_CATEGORY_ITEM: str = (
    "a.universGroup__CategoryLink-sc-6qd6g7-9.iUtWKS"
)

SELECTOR_CATEGORY_SECTION_LIST = (
    "li.universGroup__UniverseGroupItemComponent-sc-6qd6g7-3.dTahsv"
)
SELECTOR_CATEGORY_SECTION_LABEL = (
    "span.universGroup__UniverseGroupLabel-sc-6qd6g7-10.gKaSAR"
)
SELECTOR_CATEGORY_SUBCATEGORY_LINK = "a.universGroup__CategoryLink-sc-6qd6g7-9.iUtWKS"
SELECTOR_MENU_WRAPPER = "div.menuUniverse__Wrapper-sc-10tgqhe-0"


@contextmanager
def browser_context(
    headless: bool = False,
    remote_debugging: bool = False,
    slow_mo: int = 50,
    user_agent: Optional[str] = None,
    viewport: Optional[dict] = None,
    bypass_csp: bool = False,
):
    with sync_playwright() as p:
        browser = (
            p.firefox.launch(headless=headless, slow_mo=slow_mo)
            if not remote_debugging
            else p.chromium.connect_over_cdp("http://localhost:3002/", slow_mo=slow_mo)
        )
        ctx = browser.new_context(
            user_agent=user_agent,
            # bypass_csp=bypass_csp,
            # viewport={"width": 1280, "height": 800},
        )

        yield ctx
        browser.close()


def _get_rendered_html(page: Page, selector: str | None = None) -> BeautifulSoup:
    """
    Extracts product categories using BeautifulSoup after Playwright loads them
    """

    if selector:
        content = page.query_selector(selector)
        if content:
            html = content.inner_html()
            return BeautifulSoup(html, "html.parser")

        print(
            f"[ERROR] Content cannot be None. Perhaps, selector {selector} does not exist in the right place."
        )
    html = page.content()
    return BeautifulSoup(html, "html.parser")


def scrape_url(
    url: str,
    headless: bool = False,
    remote_debugging: bool = False,
    debug: bool = False,
    slow_mo: int = 40,
    wait_for_load: int = 3000,
    to_excel: bool = False,
    output_dir: Path | None = None,
    send_notification: bool = False,
    default_wait_behaviour: None = None,
) -> None:
    """
    Scrape the content of the URL using playwright
    """
    try:
        with browser_context(
            headless=headless,
            user_agent=_USER_AGENT,
            bypass_csp=True,
        ) as ctx:
            page = ctx.new_page()

            page.goto(url, wait_until="domcontentloaded")

            if debug and wait_for_load > 0:
                page.wait_for_timeout(wait_for_load)

            # logger.info("Checking for page response")
            print("Checking for page response")

            _dropdown_container: ElementHandle | None = page.query_selector(
                SELECTOR_HOMEPAGE_PRODUCTS_COLUMN
            )

            # TODO: we start performing actions in here
            # perhaps, an entrypoint function
            if page.is_visible(SELECTOR_HOMEPAGE_PRODUCTS_COLUMN):
                print("[INFO] Homepage Products Column is Visible")
                entrypoint(page, index=_dropdown_container)

                # excel file are stored directly on host system if output dir is not specified
                # TODO: write logic later - Lower priority
                if to_excel:
                    pass

            # if send notification is enabled, and scraping is successful - then drop a notification
            # TODO: write logic later - Lower priority

    except (PlaywrightError, TimeoutError) as play_err:
        logger.exception(f"Error scraping URL: {play_err}")


def extract_dropdown_items():
    pass


def scrape_product_listing_index():
    pass


def find_extract_product_overview_meta():
    pass


def scrape_product_details():
    pass


def extract_categories_from_homepage(
    page: Page, storage_: Optional[_ResponseData] = None
):
    print("[INFO] Waiting for menu universe wrapper...")
    page.wait_for_selector(SELECTOR_MENU_WRAPPER, timeout=10000)

    print("[INFO] Hovering menu universe wrapper to reveal dropdowns...")
    page.hover(SELECTOR_MENU_WRAPPER)
    page.wait_for_timeout(1500)

    # Now query inside this container
    wrapper = page.query_selector(SELECTOR_MENU_WRAPPER)
    section_nodes = wrapper.query_selector_all(SELECTOR_CATEGORY_SECTION_LIST)

    print(f"[INFO] Found {len(section_nodes)} category sections.")

    categories = []
    for section_handle in section_nodes:
        section_name_handle = section_handle.query_selector(
            SELECTOR_CATEGORY_SECTION_LABEL
        )
        section_name = (
            section_name_handle.inner_text().strip()
            if section_name_handle
            else "Unknown Section"
        )
        subcategory_handles = section_handle.query_selector_all(
            SELECTOR_CATEGORY_SUBCATEGORY_LINK
        )
        subcategories = []
        for sub_handle in subcategory_handles:
            name = sub_handle.inner_text().strip()
            href = sub_handle.get_attribute("href") or "#"
            subcategories.append({"name": name, "url": href})

        categories.append({"section": section_name, "subcategories": subcategories})

    print(categories)

    if storage_ is not None:
        storage_["categories"] = categories

    print(f"[INFO] Extracted {len(categories)} top-level sections.")


def entrypoint(page: Page, index: Optional[ElementHandle] = None) -> None:
    """
    Peforms a set of operations taking the page as the input
    """

    print("[INFO] Attempting to perform scrapping...")
    scraped_data: _ResponseData = {}

    if not index:
        page.wait_for_selector(SELECTOR_HOMEPAGE_PRODUCTS_COLUMN)

    # we find the 'Product' dropdowns and scrape its category information recursively for both columns
    # we begin scraping right from our dropdown container
    extract_categories_from_homepage(page, storage_=scraped_data)

    # then we go into each product category listing (which is like a module index, a product catalog index) page, within a dropdown and scrape all information
    # keeping the heirachy in-tact
    # for category in scraped_data.get("categories", []):
    #     scrape_product_listing_index(
    #         page, category_url=category[url], storage_=category
    #     )

    # then we proceed to go into the respective 'Product' Index Detailed Overview Listing page, all available products per index
    # while sticking keeping heirachy in-place
    # find_extract_product_overview_meta()

    # then we finally click each 'Product' itself (which is now like Amazon page), then we scrape peculiar information - Images, product information, merchant information, tags, descriptions, and whatnots
    # scrape_product_details()


if __name__ == "__main__":
    scrape_url(url, headless=False)
