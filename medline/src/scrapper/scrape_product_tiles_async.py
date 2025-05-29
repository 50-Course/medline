import asyncio
from typing import Optional
from warnings import deprecated

from playwright.async_api import (
    ElementHandle,
    JSHandle,
    Locator,
    Page,
    async_playwright,
)

from .utils import extract_product_link_from_tile


async def scrape_product_overview_tiles(page: Page) -> list:
    """
    Entrypoint function to scrape all product tiles belonging to an index entry
    """
    result_data = []

    product_tiles = await page.query_selector_all(".product-tile")
    tiles_count = len(product_tiles)

    if tiles_count:
        print(f"[INFO] Found {tiles_count} tiles")

        for tile in product_tiles:
            tile_data = await scrape_tile_data(tile)
            if tile_data:
                result_data.append(tile_data)

    await handle_pagination(page, result_data)
    print(f"Total tiles scraped: {len(result_data)}")
    return result_data


async def scrape_tile_data(tile: ElementHandle) -> Optional[dict]:
    """
    Responsible for extracting data from a single product tile.
    It is used for both the first page and paginated pages.
    """
    product_title = await _extract_product_title_from_tile(tile)

    # skip placeholder content
    if product_title and "{{" in product_title:
        print("[DEBUG] Placeholder product title discovered... skippng...")
        return None

    product_data = {
        "manufacturer_img": await _extract_manufacturer_img(tile),
        "tile_img": await _extract_tile_img(tile),
        "tile_description": await _extract_short_form_tile_desc(tile),
        "has_video": await _has_video_tag(tile),
        "features": await _extract_product_features(tile),
        "product_link": await _extract_product_link(tile),
    }
    return product_data


async def _extract_product_title_from_tile(tile: ElementHandle) -> Optional[str]:
    title_element = await tile.query_selector("h3.short-name")
    product_title = (
        (await title_element.inner_text()).strip() if title_element else None
    )
    return product_title


async def _extract_short_form_tile_desc(tile: ElementHandle) -> str:
    description_element = await tile.query_selector("p.description-text")
    description = (
        (await description_element.inner_text()).strip() if description_element else ""
    )
    return description


async def _extract_product_features(tile: ElementHandle) -> list:
    feature_elements = await tile.query_selector_all(
        "div.feature-values-container span"
    )
    features = (
        [(await feature.inner_text()).strip() for feature in feature_elements]
        if feature_elements
        else []
    )
    return features


async def _extract_product_link(tile: ElementHandle) -> str:
    product_link = await extract_product_link_from_tile(tile)
    if product_link:
        return product_link


async def _extract_tile_img(tile: ElementHandle) -> dict:
    tile_img_element = await tile.query_selector(".inset-img img")
    tile_img_src = (
        await tile_img_element.get_attribute("src") if tile_img_element else None
    )
    tile_img_alt = (
        await tile_img_element.get_attribute("alt") if tile_img_element else None
    )
    return {"img_src": tile_img_src, "img_alt": tile_img_alt}


async def _has_video_tag(tile: ElementHandle) -> bool:
    video_tag = await tile.query_selector(
        ".icon-big video"
    ) or await tile.query_selector(".new-video")
    return True if video_tag else False


async def _extract_manufacturer_img(tile: ElementHandle) -> dict:
    manufacturer_img = await tile.query_selector("a.logo img")
    logo_src = await manufacturer_img.get_attribute("src") if manufacturer_img else ""
    logo_alt = await manufacturer_img.get_attribute("alt") if manufacturer_img else ""
    return {"img_src": logo_src, "img_alt": logo_alt}


async def scrape_paginated_data(page_url: str, result_data: list):
    """
    Visits a paginated page and scrapes the product tiles.
    It reuses the `scrape_tile_data` function for extracting product tile data.
    """
    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch()
            page = await browser.new_page()

            print(f"[INFO] Visiting paginated page: {page_url}")
            await page.goto(page_url, wait_until="domcontentloaded", timeout=65000)

            print(f"[INFO] Visit successful to paginated page: {page_url}")
            product_tiles = await page.query_selector_all(".product-tile")

            for tile in product_tiles:
                tile_data = await scrape_tile_data(tile)
                if tile_data:
                    result_data.append(tile_data)

            await browser.close()
    except Exception as e:
        print(f"[ERROR] Failed to scrape page {page_url}: {e}")


async def handle_pagination(page: Page, result_data: list):
    """
    Handle pagination by visiting all pages and collecting product tile data.
    """
    pagination_links = await get_pagination_links(page)

    if not pagination_links:
        print("[INFO] No pagination found.")
        return

    # Parallelize scraping across all pages (except the first page)
    tasks = []
    for link in pagination_links[1:]:  # Skip the first page (already scraped)
        tasks.append(scrape_paginated_data(link, result_data))

    await asyncio.gather(*tasks)


async def get_pagination_links(page: Page) -> list:
    pagination_elements = await page.query_selector_all("div.pagination-wrapper a")
    pagination_links = list()

    for elem in pagination_elements:
        link = await elem.get_attribute("href")
        if link:
            pagination_links.append(link)

    return pagination_links


async def run_playwright():
    # index_entry_url: str = "https://www.medicalexpo.com/medical-manufacturer/adjustable-weight-training-bench-29045.html"  # url without pagination
    index_entry_url: str = "https://www.medicalexpo.com/medical-manufacturer/exercise-bike-4969.html"  # url with paginated results
    async with async_playwright() as p:
        browser = await p.firefox.launch()
        page = await browser.new_page()
        print(f"[INFO] Attempting to visit index: {index_entry_url}")
        await page.goto(index_entry_url, wait_until="domcontentloaded", timeout=65000)
        print(f"[INFO] Index visit successful: {index_entry_url}")
        await scrape_product_overview_tiles(page)


asyncio.run(run_playwright(), debug=True)
