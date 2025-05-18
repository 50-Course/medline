import asyncio
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, List, Optional

from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from playwright.async_api import Locator, Page, async_playwright

from .constants import USER_AGENTS as BROWSER_AGENTS
from .constants import url as BASE_URL


def get_random_user_agent() -> str:
    # gets a randomized browser agent
    return random.choice(BROWSER_AGENTS)


async def human_delay(min_=0.8, max_=2.5) -> None:
    await asyncio.sleep(random.uniform(min_, max_))


async def retry_with_backoff(coro: Callable, retries=3, delay=2):
    # extends the "core" concept of retry but with exponential backoff
    # and usable with any functtion
    for i in range(retries):
        try:
            return await coro()
        except Exception:
            await asyncio.sleep(delay * 2**i)
    raise RuntimeError("All retries failed")


async def goto_with_retry(
    page: Page, target_url: str, retries: int = 3, delay: int = 2
):
    # direct implement of page.goto but with a retry logic
    for i in range(retries):
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=10000)
            return
        except Exception as e:
            print(f"[WARN] Failed loading {BASE_URL}, retry {i + 1}/{retries}: {e}")
            await asyncio.sleep(delay * (2**i))


async def fallback_locator(
    page: Page,
    selectors: List[str],
    *,
    scope: Optional[Locator] = None,
    logger_func: Optional[Callable[[str], None]] = None,
    fallback_attrs: Optional[List[Dict[str, str]]] = None,
) -> Locator:
    """
    Try multiple selectors in order until one matches at least one element.
    Returns the first matching Locator.
    Raises ValueError if none match.
    """
    base = scope or page

    for selector in selectors:
        try:
            loc = base.locator(selector)
            if await loc.count() > 0:
                if logger_func:
                    logger_func(f"[→] Using selector: {selector}")
                return loc
        except Exception:
            continue

    # fallback to using attribute value for matching
    if fallback_attrs:
        for attr in fallback_attrs:
            tag_ = attr.get("tag", "*")
            key_ = attr.get("attr")
            value_ = attr.get("value")

            if key_ and value_:
                # build the expression
                expr = f"{tag_}[{key_}='{value_}']"

                try:
                    locator = base.locator(expr)
                    if await locator.count() > 0:
                        return locator
                except Exception:
                    # skip
                    continue

    raise ValueError(f"No selectors matched any elements: {selectors}")


@asynccontextmanager
async def browser_context(
    headless: bool = False,
    remote_debugging: bool = False,
    slow_mo: int = 50,
    user_agent: Optional[str] = None,
    viewport: Optional[dict] = None,
    bypass_csp: bool = False,
):
    async with async_playwright() as p:
        _args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--disable-features=IsolateOrigins,site-per-process",
            "--window-size=1280,800",
            "--start-maximized",
        ]

        # browser = await p.chromium.launch(headless=headless, slow_mo=slow_mo, args=_args)
        browser = await p.firefox.launch(headless=headless, slow_mo=slow_mo)
        ctx = await browser.new_context(
            # user_agent=user_agent,
            # viewport=viewport or {"width": 1280, "height": 800},
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,
        )
        try:
            yield ctx
        finally:
            await browser.close()


async def _get_rendered_html(page: Page, selector: str | None = None) -> BeautifulSoup:
    if selector:
        content = await page.query_selector(selector)
        if content:
            html = await content.inner_html()
            return BeautifulSoup(html, "html.parser")
        print(f"[ERROR] Selector {selector} did not return content.")
    html = await page.content()
    return BeautifulSoup(html, "html.parser")


def write_category_to_excel(
    categories: List[Dict[str, Any]],
    filename: str = "scraped_expo_data.xlsx",
    output_dir: Path | None = None,
):
    # output_path = Path(output_dir) / filename if output_dir else Path(filename)

    if output_dir is None:
        base_dir = Path(__file__).resolve().parent
        output_dir = base_dir / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename

    wb = Workbook()
    worksheet = wb.active
    worksheet.title = "CATEGORIES CATALOG"

    headers = ["Category", "Subcategory", "URL"]
    worksheet.append(headers)

    for category in categories:
        category_name = category["section"]
        for sub in category["subcategories"]:
            worksheet.append([category_name, sub["name"], sub["url"]])

    # Optional: auto-adjust column widths
    for col in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        adjusted_width = max_length + 2
        col_letter = get_column_letter(col[0].column)  # type: ignore
        worksheet.column_dimensions[col_letter].width = adjusted_width

    wb.save(output_path)
    print(f"[✓] Excel file saved to: {output_path}")


# def write_category_to_excel(
#     categories: list[dict], filename: str = "categories.xlsx"
# ) -> None:
#     wb = Workbook()
#
#     # Remove default sheet created automatically
#     default_sheet = wb.active
#     wb.remove(default_sheet)  # type: ignore
#
#     for category in categories:
#         section_name = category["section"][:31]
#         ws = wb.create_sheet(title=section_name)
#
#         # attah headers
#         ws.append(["Subcategory Name", "URL"])
#
#         # write the subcategories into respective section pages
#         for subcat in category.get("subcategories", []):
#             ws.append([subcat["name"], subcat["url"]])
#
#         # set column widit
#         for col in range(1, 3):
#             max_length = max(
#                 (len(str(cell.value)) for cell in ws[get_column_letter(col)]),
#                 default=10,
#             )
#             ws.column_dimensions[get_column_letter(col)].width = max_length + 5
#
#     wb.save(filename)
#     print(f"[INFO] Saved Excel file: {filename}")
