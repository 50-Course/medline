import asyncio
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, List, Optional

from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from playwright.async_api import Browser, BrowserContext
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from .constants import (SELECTOR_CATEGORY_ITEM, SELECTOR_CATEGORY_LABEL,
                        SELECTOR_CATEGORY_LABEL_SAFE,
                        SELECTOR_HOMEPAGE_PRODUCTS_COLUMN,
                        SELECTOR_INDEX_ENTRY_IMAGE, SELECTOR_INDEX_ENTRY_ITEM,
                        SELECTOR_INDEX_ENTRY_LINK, SELECTOR_INDEX_ENTRY_TITLE,
                        SELECTOR_INDEX_LIST_CONTAINER,
                        SELECTOR_INDEX_PAGE_HEADER,
                        SELECTOR_PRODUCTS_INNERMOST_CONTAINER,
                        SELECTOR_SUBCATEGORY_LINK,
                        SELECTOR_SUBCATEGORY_LINK_SAFE)
from .constants import _ResponseData as Response
from .utils import (browser_context, fallback_locator, get_random_user_agent,
                    goto_with_retry, human_delay, retry_with_backoff,
                    write_category_to_excel)

logger = logging.getLogger(__name__)

url: str = "https://www.medicalexpo.com/"


async def scrape_url(
    url: str,
    headless: bool = False,
    debug: bool = False,
    slow_mo: int = 40,
    wait_for_load: int = 3000,
    to_excel: bool = False,
    output_dir: Path | None = None,
    send_notification: bool = False,
) -> None:
    try:
        async with browser_context(
            headless=headless,
            user_agent=get_random_user_agent(),
            bypass_csp=True,
        ) as ctx:
            page = await ctx.new_page()

            await stealth_async(page)

            await retry_with_backoff(lambda: page.goto(url, wait_until="networkidle"))
            if debug and wait_for_load > 0:
                await page.wait_for_timeout(wait_for_load)

            print("Checking for page response")

            parent_container_visble = await page.is_visible(
                SELECTOR_HOMEPAGE_PRODUCTS_COLUMN
            )
            if parent_container_visble:
                print("[INFO] Parent Container is Visible")
                await entrypoint(page, to_excel=to_excel)

    except (PlaywrightError, TimeoutError) as play_err:
        logger.exception(f"Error scraping URL: {play_err}")


async def scrape_product_listing_index(
    page: Page,
    subcategory_name: str,
    subcategory_url: str,
    base_url: str = "https://www.medicalexpo.com",
    storage_: Optional[Response] = None,
    timeout: Optional[int] = 30000,
) -> None:
    print(f"[INFO] Navigating to subcategory page: {subcategory_url}")
    await page.goto(subcategory_url, timeout=timeout)
    await page.wait_for_selector(SELECTOR_INDEX_PAGE_HEADER)

    page_heading = await (
        await page.query_selector(SELECTOR_INDEX_PAGE_HEADER)
    ).inner_text()
    if page_heading.lower() != subcategory_name.lower():
        print(
            f"[WARN] Page mismatch: Expected '{subcategory_name}', got '{page_heading}'"
        )
        return

    await page.wait_for_selector(SELECTOR_INDEX_LIST_CONTAINER)
    _items = await page.query_selector_all(SELECTOR_INDEX_ENTRY_ITEM)
    index_entries = []

    for entry in _items:
        a_tag = await entry.query_selector(SELECTOR_INDEX_ENTRY_LINK)
        title_node = await a_tag.query_selector(SELECTOR_INDEX_ENTRY_TITLE)
        img_node = await a_tag.query_selector(SELECTOR_INDEX_ENTRY_IMAGE)

        title = await title_node.inner_text() if title_node else "Untitled"
        await human_delay(0.5, 1.5)
        href = await a_tag.get_attribute("href") if a_tag else "#"
        img_src = await img_node.get_attribute("src") if img_node else ""
        img_alt = await img_node.get_attribute("alt") if img_node else ""

        index_entries.append(
            {
                "title": title,
                "href": href,
                "image_meta": {"src": img_src, "alt": img_alt},
            }
        )

    print(index_entries)
    if storage_ is not None:
        storage_["index_entries"] = index_entries

    print(
        f"[INFO] Extracted {len(index_entries)} index entries from '{subcategory_name}'"
    )


async def extract_categories(
    page: Page, logger_func: Optional[Callable[[str], None]] = None
):
    logger_func = logger_func or print

    logger_func("[*] Looking for top-level category items...")
    section_items = await fallback_locator(
        page,
        [
            "li[data-cy^='universGroupItemCy_']",
            SELECTOR_CATEGORY_ITEM,
        ],
    )
    section_items = await section_items.all()

    logger_func(f"[+] Found {len(section_items)} top-level category items")

    categories: List[Dict[str, Any]] = []

    for i, section in enumerate(section_items):
        logger_func(f"\n[→] Processing category index {i}")

        try:
            label_node = await fallback_locator(
                page,
                scope=section,
                selectors=[
                    ":scope span[class*='UniverseGroupLabel']",
                    ":scope span[class*='universeGroup__UniverseGroupLabel']",
                    ":scope span",
                ],
            )
            print(f"[INFO] {label_node}")
            category_name = (await label_node.inner_text()).strip()
            logger_func(f"    [✓] Category name: '{category_name}'")
        except Exception as e:
            logger_func(f"    [!] Failed to extract category name: {e}")
            continue

        # expand dropdown
        try:
            # wait 5 secs
            await section.wait_for(timeout=5000)
            await section.click(timeout=2000)
            await human_delay(0.2)
            logger_func("    [✓] Clicked to expand dropdown")
        except Exception as e:
            logger_func(f"    [!] Failed to expand category '{category_name}': {e}")

        subsections = await section.locator("ul li a").all()
        logger_func(f"[→] Section: {category_name} ({len(subsections)} subcategories)")

        subcategories = []
        for subsection in subsections:
            try:
                name = (await subsection.inner_text()).strip()
                href = await subsection.get_attribute("href")
                if name and href:
                    subcategories.append({"name": name, "url": href})
                    logger_func(f"    [✓] Subsection: {name}")
            except Exception as e:
                logger_func(f"    [!] Failed to extract subsection link: {e}")

        categories.append(
            {
                "section": category_name,
                "subcategories": subcategories,
            }
        )

        logger_func(
            f"[→] Completed Section: {category_name} ({len(subsections)} subcategories)"
        )

    logger_func("\n[✓] Completed extracting all categories.")
    return categories


async def extract_categories_from_homepage(
    page: Page, storage_: Optional[Response] = None
):
    print("[INFO] Entered inside the function: extract_categories_from_homepage")

    try:
        await page.wait_for_selector(
            SELECTOR_PRODUCTS_INNERMOST_CONTAINER, state="attached", timeout=15000
        )
        print("[INFO] Selector attached to DOM")
        container = page.locator(SELECTOR_PRODUCTS_INNERMOST_CONTAINER)
        is_visible = await container.is_visible()

        print(f"[INFO] Container visibility: {is_visible}")

        if not is_visible:
            print("[INFO] Element is attached but not visible")
            return

        print("[INFO] Element is attached AND visible. Proceeding.")
    except (PlaywrightTimeoutError, Exception):
        print("[ERROR] Innermost container never appeared in DOM")
        return

    try:
        categories = await extract_categories(page)
    except Exception as e:
        print(f"[ERROR] Failed to extract categories: {e}")
        return

    if storage_:
        storage_["categories"] = categories

    print(f"[INFO] Extracted {len(categories)} top-level sections.")
    return categories


async def entrypoint(page: Page, to_excel=False) -> None:
    print("[INFO] Attempting to perform scrapping...")
    scraped_data: Response = {}

    # categories = await extract_categories_from_homepage(page, storage_=scraped_data)
    categories = await extract_categories_from_homepage(page)

    if categories:
        scraped_data["categories"] = categories

    print("[INFO] Completed Extract")

    # for section in scraped_data["categories"]:
    #     for subsection in section["subcategories"]:
    #         await scrape_product_listing_index(
    #             page, subsection["name"], subsection["url"], storage_=subsection
    #         )

    print(f"[INFO] {scraped_data}")
    # breakpoint()

    if to_excel and "categories" in scraped_data:
        print("[DEBUG] Writing extracted categories to Excel file...")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        write_category_to_excel(
            scraped_data["categories"], filename=f"scraped_expo_data_{timestamp}.xlsx"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(scrape_url(url, headless=False, to_excel=True))
