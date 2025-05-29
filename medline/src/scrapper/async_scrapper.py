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

from src.scrapper.scrape_product_data_async import extract_product_data_async
from src.scrapper.scrape_product_tiles_async import scrape_product_overview_tiles

from .constants import (
    SELECTOR_CATEGORY_ITEM,
    SELECTOR_CATEGORY_LABEL,
    SELECTOR_CATEGORY_LABEL_SAFE,
    SELECTOR_HOMEPAGE_PRODUCTS_COLUMN,
    SELECTOR_INDEX_ENTRY_IMAGE,
    SELECTOR_INDEX_ENTRY_ITEM,
    SELECTOR_INDEX_ENTRY_LINK,
    SELECTOR_INDEX_ENTRY_TITLE,
    SELECTOR_INDEX_LIST_CONTAINER,
    SELECTOR_INDEX_PAGE_HEADER,
    SELECTOR_PRODUCTS_INNERMOST_CONTAINER,
    SELECTOR_SUBCATEGORY_LINK,
    SELECTOR_SUBCATEGORY_LINK_SAFE,
)
from .constants import _ResponseData as Response
from .utils import (
    browser_context,
    extract_product_link_from_tile,
    fallback_locator,
    get_random_user_agent,
    goto_with_retry,
    human_delay,
    retry_with_backoff,
    write_category_to_excel,
)

# from src.scrapper.scrape_product_data_async import extract_product_data_async
# from src.scrapper.scrape_product_detail import extract_product_data


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


async def scrape_all_subcategory_indexes(ctx: BrowserContext, categories):
    sem = asyncio.Semaphore(8)
    jobs = []

    for section in categories:
        for sub in section["subcategories"]:

            async def scrape_subcategory(name=sub["name"], url=sub["url"], storage=sub):
                async with sem:
                    page = await ctx.new_page()
                    try:
                        await scrape_product_listing_index(
                            page, name, url, storage_=storage
                        )
                    except Exception as e:
                        print(f"[ERROR] Failed scraping {name}: {e}")
                    finally:
                        await page.close()

            jobs.append(scrape_subcategory())

    await asyncio.gather(*jobs)


async def scrape_product_listing_index(
    page: Page,
    subcategory_name: str,
    subcategory_url: str,
    storage_: Optional[Response] = None,
) -> None:
    print(f"[INFO] Navigating to subcategory page: {subcategory_url}")
    await retry_with_backoff(lambda: page.goto(subcategory_url))
    await page.wait_for_selector(SELECTOR_INDEX_PAGE_HEADER)

    page_heading = await (
        await page.query_selector(SELECTOR_INDEX_PAGE_HEADER)
    ).inner_text()
    if page_heading.lower() != subcategory_name.lower():
        print(
            f"[WARN] Page mismatch: Expected '{subcategory_name}', got '{page_heading}'"
        )
        return

    # Wait for parent container
    await page.wait_for_selector("div#category-group ul.category-grouplist")
    group_nodes = await page.query_selector_all(
        "div#category-group ul.category-grouplist"
    )

    index_entries = []

    for group in group_nodes:
        item_nodes = await group.query_selector_all("li")
        for item in item_nodes:
            a_tag = await item.query_selector("a")
            img_tag = await item.query_selector("div.imgSubCat img")

            if not a_tag:
                continue

            name = (await a_tag.inner_text()).strip()
            href = await a_tag.get_attribute("href")
            img_src = await img_tag.get_attribute("src") if img_tag else ""
            img_alt = await img_tag.get_attribute("alt") if img_tag else ""

            index_entries.append(
                {
                    "title": name,
                    "href": href,
                    "image_meta": {
                        "src": img_src,
                        "alt": img_alt,
                    },
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


async def scrape_product_overview(
    ctx: BrowserContext, categories: List[Dict[str, Any]]
):
    sem = asyncio.Semaphore(5)

    entries_to_scrape = [
        entry
        for section in categories
        for sub in section.get("subcategories", [])
        for entry in sub.get("index_entries", [])
    ]

    async def scrape_entry(entry):
        async with sem:
            page = await ctx.new_page()
            try:
                print(f"[->] Visiting product tile index page: {entry.get('href')}")
                # # We should be instead calling the scrape all pages function
                # # on the entry link `entry[href]` and NOT THIS STUFF I HAVE BELOW
                # await scrape_product_tile_detail(page, entry, storage_=entry)

                await page.goto(
                    entry["href"], timeout=60000, wait_until="domcontentloaded"
                )

                # operation 3: scrape all product tiles in this entry
                tile_data = await scrape_product_overview_tiles(page)

                # operation 4: for each product tile link, visit and extract full product data
                full_product_details = []
                for tile in tile_data:
                    product_url = tile.get("product_link")
                    if not product_url:
                        continue
                    try:
                        print(f"[->->] Visiting product detail: {product_url}")
                        await page.goto(
                            product_url, timeout=60000, wait_until="domcontentloaded"
                        )
                        full_data = await extract_product_data_async(page)
                        full_product_details.append({**tile, **full_data})
                    except Exception as e:
                        print(
                            f"[WARN] Failed to extract full product at {product_url}: {e}"
                        )
                        continue

                entry["products"] = full_product_details
                print(f"[✓] Completed scraping for index entry: {entry.get('title')}")

            except Exception as e:
                print(
                    f"[WARN] Could not scrape product detail for {entry.get('href')}: {e}"
                )
            finally:
                await page.close()

    await asyncio.gather(*(scrape_entry(entry) for entry in entries_to_scrape))
    print("[INFO] Completed all tile + full product detail extractions.")


# NOTE: convert to async
async def extract_product_info_from_page(
    page: Page, visited: Optional[dict] = {}, storage_: Optional[Response] = None
):
    print("[INFO] entered the product info function... ")

    try:
        await page.wait_for_selector(
            "div.product-tile", timeout=50000, state="attached"
        )
        print("[INFO] Found some product tiles...")
    except Exception as e:
        print(f"[WARN] Product tiles never appeared: {e}")
        return []

    product_tiles = await page.query_selector_all("div.product-tile")

    print(f"Found: {len(product_tiles)} product tiles")
    results = []

    for tile in product_tiles:
        try:
            # Check for "See more products" tile
            see_more_element = await tile.query_selector("#nextButton span.short-name")
            if see_more_element:
                print(
                    "[INFO] This is a paginated webpage... attempting to visit other pages first"
                )
                text = (
                    (await see_more_element.inner_text())
                    .strip()
                    .lower()
                    .replace("\n", "")
                )

                if "see more" in text:
                    a_tag = await tile.query_selector("#nextButton a")
                    if a_tag:
                        next_page_url = await a_tag.get_attribute("href")
                        print(f"Redirect tile found, next page: {next_page_url}")
                        if next_page_url:
                            print(f"[TRACE] Visiting paginated URL: {next_page_url}")

                            await page.goto(next_page_url)

                            return await extract_product_info_from_page(page, visited)

            manufacturer_img = await tile.query_selector("a.logo img")
            manufacturer_name = (
                await manufacturer_img.get_attribute("alt")
                if manufacturer_img
                else None
            )
            manufacturer_logo = (
                await manufacturer_img.get_attribute("data-src")
                or await manufacturer_img.get_attribute("src")
                if manufacturer_img
                else None
            )

            title_element = await tile.query_selector("h3.short-name")
            product_title = (
                (await title_element.inner_text()).strip() if title_element else None
            )

            # Skip placeholder content
            if product_title and "{{" in product_title:
                product_title = "Unknown Title"

            model_element = await tile.query_selector("h3.short-name > span.brand")
            product_model = (
                (await model_element.inner_text()).strip() if model_element else None
            )

            model_number_element = await tile.query_selector("div.model")
            model_number = (
                (await model_number_element.inner_text()).strip()
                if model_number_element
                else None
            )

            try:
                feature_elements = await tile.query_selector_all(
                    "div.feature-values-container span"
                )
                features = (
                    [await f.inner_text() for f in feature_elements]
                    if feature_elements
                    else []
                )
            except Exception as e:
                print(f"[WARN] Could not extract features: {e}")
                features = []

            tile_img_element = await tile.query_selector(".inset-img img")
            tile_img_src = (
                await tile_img_element.get_attribute("src")
                if tile_img_element
                else None
            )
            tile_img_alt = (
                await tile_img_element.get_attribute("alt")
                if tile_img_element
                else None
            )

            price_element = await tile.query_selector("div.price span.js-price-content")
            price = (
                (await price_element.inner_text()).strip() if price_element else None
            )
            currency = (
                await price_element.get_attribute("data-currency")
                if price_element
                else None
            )

            product_link = await extract_product_link_from_tile(tile)

            try:
                description_element = await tile.query_selector("p.description-text")
                description = (
                    (await description_element.inner_text()).strip()
                    if description_element
                    else None
                )
            except Exception as e:
                logger.error(f"[ERROR]: {str(e)}", exc_info=True)
                description = None

            extracted_data = {
                "manufacturer_name": manufacturer_name,
                "manufacturer_logo": manufacturer_logo,
                "product_title": product_title,
                "product_model": product_model,
                "model_number": model_number,
                "features": features,
                "price": price,
                "currency": currency,
                "product_link": product_link,
                "tile_image_src": tile_img_src,
                "tile_image_alt": tile_img_alt,
                "tile_description": description,
            }
            results.append(extracted_data)

            if storage_ is not None and product_title:
                storage_.setdefault("products", []).append(extracted_data)

        except Exception as e:
            logger.exception(f"[WARN] Failed to extract tile: {e}", exc_info=True)
            continue

    return results


# NOTE: convert to async
async def extract_all_pages(
    ctx: BrowserContext, start_url: str, storage_: Optional[Response] = None
):
    all_results = []
    page = await ctx.new_page()
    visited = set()
    visited.add(start_url)

    # NOTE: WE DON'T WANT TO USE SYNC PLAYWRIGHT HOW CAN
    # WE MAKE THIS STUFF WORK WITH OUR EXISTING CODE?
    # LET IT RESUSE OUR EXISTING BROWSER BUT THE HANDLING OF
    # OTHER PAGES SHOULD BE DONE IN PARALLEL IF POSSIBLE
    #
    print("[INFO] attempting to visit website")
    await page.goto(start_url, timeout=60000, wait_until="domcontentloaded")
    await page.wait_for_selector("div.product-tile", timeout=15000)

    print("[INFO] page visit completed")
    results = await extract_product_info_from_page(
        page, visited=visited, storage_=storage_
    )
    all_results.extend(results)

    # paginate through additional pages
    pagination = await page.query_selector_all(".pagination-wrapper a:not(.next)")
    hrefs = []

    for anchor in pagination:
        try:
            href = await anchor.get_attribute("href")
            if href:
                # visited.add(href)
                hrefs.append(href)
        except Exception as e:
            print(f"[WARN] Failed getting href from anchor: {e}")

    for href in hrefs:
        if href in visited:
            print(f"[DEBUG] Skipping already visited: {href}")
            continue
        visited.add(href)

        try:
            print(f"Navigating to: {href}")
            await page.goto(href, timeout=60000, wait_until="domcontentloaded")
            results = await extract_product_info_from_page(
                page,
                visited=visited,  # type: ignore
                storage_=storage_,
            )
            all_results.extend(results)
        except Exception as e:
            print(f"[WARN] Failed to visit pagination link: {href}: {e}")

    await page.close()
    return all_results


# NOTE: WE DO NOT NEED THIS GUY, ITS OF NO IMPORTANCE TO US!
async def scrape_product_tile_detail(
    page: Page, entry: dict[str, Any], storage_: Optional[None] = None
):
    # OPERATION (PART 3)
    url = entry.get("href")
    if not url:
        print("[!] Product Url not found or invalid")
        return

    print(f"[-> ] Visiting product page: {url}")
    try:
        # await extract_all_pages(page.context, url, storage_=storage_)
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_selector("div.product-tile", timeout=15000)

        results = await extract_product_info_from_page(page, storage_=storage_)

        print(f"[✓] Scraped {len(results)} products from {url}")

    except Exception as e:
        print(f"[!] Failed extracting innerHTML from {url}: {e}")
        logger.error(str(e), exc_info=True)


async def entrypoint(page: Page, to_excel=False) -> None:
    print("[INFO] Attempting to perform scrapping...")
    scraped_data: Response = {}

    # categories = await extract_categories_from_homepage(page, storage_=scraped_data)

    # OPERATION 1
    categories = await extract_categories_from_homepage(page)

    if categories:
        scraped_data["categories"] = categories

    print("[INFO] Completed Extract")

    # for section in scraped_data["categories"]:
    #     for subsection in section["subcategories"]:
    #         await scrape_product_listing_index(
    #             page, subsection["name"], subsection["url"], storage_=subsection
    #         )

    # let's run it in parralel
    # Operation 2
    await scrape_all_subcategory_indexes(page.context, scraped_data["categories"])

    # OPERATION 3
    #
    # NOTE: we reuse the context from earlier, we would run this in parallel
    # however, we want to goto each url of the indexes we have
    # and extract every information of the "avaliable" products, manufacturer information,
    # tags, etc
    # we look through each and every product links of index_entries, and head out to the
    # links on there
    await scrape_product_overview(page.context, scraped_data["categories"])

    # print(f"[INFO] {scraped_data}")
    print("[INFO] Successfully scraped website")

    if to_excel and "categories" in scraped_data:
        print("[DEBUG] Writing extracted categories to Excel file...")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        write_category_to_excel(
            scraped_data["categories"], filename=f"scraped_expo_data_{timestamp}.xlsx"
        )


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="MedicalExpo Product Scraper")

    parser.add_argument(
        "--url",
        type=str,
        default="https://www.medicalexpo.com/",
        help="Target URL to scrape from.",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode.",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug Mode",
    )

    parser.add_argument(
        "--slow-mo",
        type=int,
        default=40,
        help="Slow motion delay in ms between browser actions (default: 40).",
    )

    parser.add_argument(
        "--wait-for-load",
        type=int,
        default=3000,
        help="Wait time in ms after initial page load (default: 3000).",
    )

    parser.add_argument(
        "--to-excel",
        action="store_true",
        help="Whether to write the result to Excel.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Path to directory for saving output files.",
    )

    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notification after scraping (e.g., Slack/Email/Whatsapp or Text).",
    )

    args = parser.parse_args()

    asyncio.run(scrape_url(url, headless=args.headless, to_excel=args.to_excel))
