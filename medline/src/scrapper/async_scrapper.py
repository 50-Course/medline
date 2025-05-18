import asyncio
import logging
import os
import random
import time
from contextlib import asynccontextmanager
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
                    write_categories_to_excel)

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
    # category_items = page.locator(SELECTOR_CATEGORY_ITEM)
    category_items = await fallback_locator(
        page,
        [
            "li[data-cy^='universGroupItemCy_']",
            SELECTOR_CATEGORY_ITEM,
        ],
    )
    category_items = await category_items.all()

    logger_func(f"[+] Found {len(category_items)} top-level category items")

    categories: List[Dict[str, Any]] = []

    for i, item in enumerate(category_items):
        item = item.nth(i)
        logger_func(f"\n[→] Processing category index {i}")

        try:
            label_node = item.get_attribute(
                "universGroup__UniverseGroupLabel-sc-6qd6g7-10.gKaSAR"
            )
            # label_node = await fallback_locator(
            #     page,
            #     scope=item,
            #     selectors=[
            #         "span[class*='UniverseGroupLabel']",
            #         "span[class*='universeGroup__UniverseGroupLabel']",
            #         SELECTOR_CATEGORY_LABEL_SAFE,
            #     ],
            # )
            category_name = (await label_node.inner_text()).strip()
            logger_func(f"    [✓] Category name: '{category_name}'")
        except Exception as e:
            logger_func(f"    [!] Failed to extract category name: {e}")
            continue

        # Try to click and expand dropdown
        try:
            await item.click(timeout=2000)
            await human_delay(0.2)
            logger_func("    [✓] Clicked to expand dropdown")
        except Exception as e:
            logger_func(f"    [!] Failed to expand category '{category_name}': {e}")

        subcategories = []
        try:
            # sub_links = item.locator(_SELECTOR_SUBCATEGORY_LINK_SAFE)
            sub_links = await fallback_locator(
                page,
                scope=item,
                selectors=[
                    "a[class*='CategoryLink']",
                    "a[class*='CategoryLink-sc-']",
                    SELECTOR_SUBCATEGORY_LINK_SAFE,
                ],
            )
            count_links = await sub_links.count()
            logger_func(f"    [✓] Found {count_links} subcategory links")

            for j in range(count_links):
                try:
                    link = sub_links.nth(j)
                    name = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    if name and href:
                        subcategories.append({"name": name, "url": href})
                        logger_func(f"      [+] {name} → {href}")
                except Exception as e:
                    logger_func(f"      [!] Skipped malformed subcategory link: {e}")
        except Exception as e:
            logger_func(f"    [!] Failed to collect subcategories: {e}")

        categories.append({"section": category_name, "subcategories": subcategories})

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

    # now we find all list items belonging inside this container
    # not sure if `Locator` is the best way here or `page.querySelector`
    section_items = container.locator(SELECTOR_CATEGORY_ITEM)
    section_elements = await section_items.element_handles()
    print(f"[INFO] Found {len(section_elements)} sections")
    # category_items = await page.query_selector_all(SELECTOR_CATEGORY_ITEM)

    try:
        categories = await extract_categories(page)
    except Exception as e:
        print(f"[ERROR] Failed to extract categories: {e}")
        return

    import pdb

    pdb.set_trace()

    # for index, item in enumerate(section_elements):
    # element_handle = page.locator(f"{SELECTOR_CATEGORY_ITEM} >> nth={index}")
    # print(f"[INFO] {element_handle}")
    #
    # try:
    #     # Click to expand dropdown
    #     await element_handle.click()
    #     # await human_delay(0.5, 1.2)
    # except Exception as e:
    #     print(f"[WARN] Failed to click section {index}: {e}")
    #     continue
    #
    # # Try to extract section name
    # section_label = await element_handle.locator(
    #     SELECTOR_CATEGORY_LABEL_SAFE
    # ).text_content()
    # section_name = (
    #     section_label.strip() if section_label else f"Unknown Section {index}"
    # )
    #
    # # Extract subcategory links (visible after click)
    # subcategories = []
    # sub_links = await element_handle.locator(
    #     SELECTOR_SUBCATEGORY_LINK_SAFE
    # ).element_handles()
    #
    # for link_handle in sub_links:
    #     try:
    #         name = (await link_handle.text_content() or "").strip()
    #         href = await link_handle.get_attribute("href") or "#"
    #         subcategories.append({"name": name, "url": href})
    #     except Exception as sub_err:
    #         print(
    #             f"[WARN] Failed reading subcategory in section '{section_name}': {sub_err}"
    #         )
    #
    # print(f"[INFO] '{section_name}' → {len(subcategories)} subcategories")

    # for item in category_items:
    #     section_label = await item.query_selector(SELECTOR_CATEGORY_LABEL)
    #     section_name = (
    #         await section_label.inner_text() if section_label else "Unknown Section"
    #     )
    #
    #     await human_delay(0.5, 1.2)
    #
    #     subcategory_links = await item.query_selector_all(SELECTOR_SUBCATEGORY_LINK)
    #     subcategories = []
    #
    #     for sub_handle in subcategory_links:
    #         name = await sub_handle.inner_text()
    #         href = await sub_handle.get_attribute("href") or "#"
    #         subcategories.append({"name": name, "url": href})
    #
    #     print(f"[INFO] '{section_name}' → {len(subcategories)} subcategories")
    #     categories.append({"section": section_name, "subcategories": subcategories})

    if storage_ is not None:
        storage_["categories"] = categories

    print(f"[INFO] Extracted {len(categories)} top-level sections.")


async def entrypoint(page: Page, to_excel=False) -> None:
    print("[INFO] Attempting to perform scrapping...")
    scraped_data: Response = {}

    await extract_categories_from_homepage(page, storage_=scraped_data)

    print("[INFO] Completed Extract")

    # Uncomment to test deeper levels
    # for section in scraped_data["categories"]:
    #     for subsection in section["subcategories"]:
    #         await scrape_product_listing_index(
    #             page, subsection["name"], subsection["url"], storage_=subsection
    #         )

    if to_excel and "categories" in scraped_data:
        write_categories_to_excel(
            scraped_data["categories"], filename="scraped_categories.xlsx"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(scrape_url(url, headless=False))
