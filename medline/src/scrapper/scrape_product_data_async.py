"""
Allows us to extract the full product data of a given product
"""

import asyncio
from typing import Literal, Optional

from playwright.async_api import Page, async_playwright
from playwright.sync_api import BrowserContext


async def extract_product_data_async(page: Page) -> dict:
    data = {}
    # await page.wait_for_load_state("networkidle")

    title, model = await _extract_product_title_and_model(page)
    data["title"] = title
    data["model"] = model

    # 2. Tags / Attributes
    data["tags"] = await _extract_product_attr_tags(page)

    # 3. Description
    data["description"] = await _extract_full_product_description(page)

    # 4. Characteristics
    data["characteristics"] = await _extract_characteristics_table(page)

    # 5. Catalog
    catalog_header = page.locator('h2:has-text("Catalogs")').first
    data["catalog_available"] = None
    if await catalog_header.count():
        p = catalog_header.locator("xpath=following::p").first
        if await p.count():
            text = await p.inner_text()
            data["catalog_available"] = "no catalogs" not in text.lower()

    # 6. Video
    data["video_url"] = await _extract_video_url(page)

    # 7. Manufacturer Info
    manu_name = page.locator('div[class*="supplierDetails__Name"]')
    manu_location = page.locator('div[class*="supplierDetails__Location"]')
    data["manufacturer"] = {
        "name": (await manu_name.inner_text()).strip() if manu_name else None,
        "location": (await manu_location.inner_text()).strip()
        if manu_location
        else None,
    }
    # data["manufacturer"] = await _extract_manufacturer_info(page)

    # 8. Rating
    data["manufacturer"]["rating"] = await _extract_manufacturer_rating(page)

    # 9. Images
    data["images"] = await _extract_product_img_urls(page)

    # 10. Product Price
    price, currency = await _extract_product_price(page)
    data["indicative_price"] = price
    data["currency"] = currency

    return data


async def _extract_full_product_description(page: Page) -> str:
    desc_element = page.locator(".sc-3fi1by-0.hlEuXW")
    # await desc_element.wait_for(state="attached", timeout=60000)

    description = await desc_element.inner_text()
    return description or "No description available"


async def _extract_product_title_and_model(page: Page) -> tuple[str | None, str | None]:
    title_block = await page.query_selector('span[class^="sc-2mcr2-0"]')

    if not title_block:
        return "Unknown Product Title", "Unknown Product Model"

    print("[INFO] Found title block")
    spans = await title_block.query_selector_all("span")

    title, model = "Unknown Product Title", "Unknown Product Model"

    if len(spans) > 0:
        title = await spans[0].inner_text()
    if len(spans) > 1:
        model = await spans[1].inner_text()

    return title, model  # type: ignore


async def _extract_corresponding_catalog(page: Page):
    pass


async def _extract_product_attr_tags(page: Page) -> list[str]:
    tag_elements = await page.query_selector_all(
        'div[class^="sc-cw67gy-0"] span[class^="sc-cw67gy-1"]'
    )
    return [await el.inner_text() for el in tag_elements]


async def _extract_characteristics_table(page: Page) -> dict:
    characteristics = {}
    characteristics_table = await page.query_selector("dl.sc-mgb5nu-0.gedvae")

    if characteristics_table:
        print("[INFO] Found Characterististics table")
        dt_elements = await characteristics_table.query_selector_all("dt")
        dd_elements = await characteristics_table.query_selector_all("dd")
        for dt, dd in zip(dt_elements, dd_elements):
            key = await dt.inner_text()
            value = await dd.inner_text()
            characteristics[key.strip()] = value.strip()
    return characteristics


async def _extract_video_url(page: Page) -> str | None:
    video_url = None
    video_header = page.locator('h2:has-text("VIDEO")').first or page.locator(
        "div.sc-1w8z6ht-5.cBFfGP video"
    )
    if await video_header.count():
        print(f"[INFO] Found video container for: {page.url}")

        video_src = video_header.locator(
            "xpath=following::video/source"
        ).first or page.locator("div.sc-1w8z6ht-5.cBFfGP video source")

        if await video_src.count():
            print(f"[INFO] Found Video element for {page.url}")

            video_url = await video_src.get_attribute("src", timeout=60000)
    return video_url


async def _extract_manufacturer_info(page: Page) -> dict:
    manu_name = page.locator('div[class*="supplierDetails__Name"]')
    manu_location = page.locator('div[class*="supplierDetails__Location"]')
    manufacturer_data = {
        "name": (await manu_name.inner_text(timeout=60000)).strip()
        if manu_name
        else None,
        "location": (await manu_location.inner_text()).strip()
        if manu_location
        else None,
    }
    return manufacturer_data


async def _extract_manufacturer_rating(page: Page) -> int:
    man_selector = "xpath=//div[contains(@class, 'supplierDetails__RatingDetails-sc-cmi9pt-12 dVOoeb rating')]//span[contains(@style, 'visibility: hidden')]"
    man_rating = page.locator(man_selector)
    return await man_rating.count()


async def _extract_product_img_urls(page: Page) -> list:
    image_urls = []
    images = await page.query_selector_all(
        'div[class*="imageViewer__NavPicsWrapper"] img[data-src$=".jpg"]'
    )
    if images:
        print(f"[INFO] Found the product images for: {page.url}")
        seen = set()
        for img in images:
            src = await img.get_attribute("data-src")
            if src and src not in seen:
                seen.add(src)
                image_urls.append(src)
    return image_urls


async def _extract_product_price(
    page: Page,
) -> tuple[str | None, Literal["USD"] | None]:
    """
    Extracts product price and currency if present.
    Returns (price, currency) or (None, None).
    """
    ""
    try:
        price_el = page.locator('div[class*="mainSupplier__PriceValue"] span')
        # failsafe, incase, there is no price on the page
        if await price_el.count() > 0:
            raw_price = await price_el.inner_text()
            if raw_price:
                raw_price = raw_price.strip()
                currency = "USD" if "$" in raw_price else None
                return raw_price, currency
        else:
            print(f"[INFO] Price element not found on {page.url}")
    except Exception as e:
        print(f"[WARN] Exception during price extraction: {e}")

    return None, None


async def run_playwright():
    product_url: str = (
        # "https://www.medicalexpo.com/prod/tunturi/product-122229-856618.html"
        "https://www.medicalexpo.com/prod/vitrex-medical-s/product-110882-954642.html"  # product link with catalog
    )
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        print(f"[INFO] Attempting to visit: {product_url}")
        await page.goto(product_url, wait_until="domcontentloaded", timeout=65000)
        print(f"[INFO] Visit successful: {product_url}")
        product_data = await extract_product_data_async(page)

        if product_data:
            print(f"[INFO] Successfully scrapped product: {product_url}")
            # print(product_data)


asyncio.run(run_playwright(), debug=True)
