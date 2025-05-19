from typing import Annotated

USER_AGENTS = [
    "Mozilla/5.0 ... Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.3240.64",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.88 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/21.0 Chrome/110.0.5481.154 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/136.0.7103.91 Mobile/15E148 Safari/604.1",
]

url: str = "https://www.medicalexpo.com/"

_ResponseData = Annotated[dict, "Prettified JSON response"]

# PAGE 2 =====================================
SELECTOR_INDEX_PARENT_CONTAINER = 'div.hoverizeList:nth-child(1)'
SELECTOR_INDEX_LIST_CONTAINER = "ul.category-grouplist"
SELECTOR_INDEX_ENTRY_ITEM = "ul.category-grouplist > li"
SELECTOR_INDEX_ENTRY_LINK = "a"
SELECTOR_INDEX_ENTRY_TITLE = "p.subCatTitle"
SELECTOR_INDEX_ENTRY_IMAGE = "div.imgSubCat > img"
SELECTOR_INDEX_PAGE_HEADER = "h1#category"

# Page 1 (Homepage) ==========================
SELECTOR_MENU_WRAPPER = "div.menuUniverse__Wrapper-sc-10tgqhe-0"

# The parent row holding two columns
# The inner most element that contains both columns
SELECTOR_PRODUCTS_INNERMOST_CONTAINER = ".sc-10tgqhe-0"

# this container is two steps above the `SELECTOR_PRODUCTS_INNERMOST_CONTAINER`
SELECTOR_PRODUCTS_INNERMOST_PARENT_CONTAINER = ".sc-6qd6g7-15"

# The two major left and right section columsn on the homepage
SELECTOR_CATEGORY_COL_LEFT = ".sc-ztyvp1-0:nth-child(1)"
SELECTOR_CATEGORY_COL_RIGHT = ".sc-ztyvp1-0:nth-child(2)"
# Each column inside the row (7 items per column)
SELECTOR_CATEGORY_COLUMN = ".sc-6qd6g7-6"

# The parent container of all product columns
SELECTOR_HOMEPAGE_PRODUCTS_COLUMN = "div.sc-19e28ua-1.eZHbVe"

# The parent row holding two columns
# SELECTOR_CATEGORY_ROW = "div.row__Row-sc-wfit35-0.universGroup__MenuRow-sc-6qd6g7-6"


SELECTOR_CATEGORY_LABEL_SAFE = "span[class*='UniverseGroupLabel']"
SELECTOR_SUBCATEGORY_LINK_SAFE = "a[class*='CategoryLink']"

# Each category item inside a column
SELECTOR_CATEGORY_ITEM = ".sc-6qd6g7-3"

# Label inside the category item (top-level category name)
SELECTOR_CATEGORY_LABEL = "span.universGroup__UniverseGroupLabel-sc-6qd6g7-10.gKaSAR"

# Dropdown UL containing subcategories (must hover or click first)
SELECTOR_SUBCATEGORY_LIST = "ul.universGroup__CategoryUl-sc-6qd6g7-4.iCVouy"

# Each subcategory LI
SELECTOR_SUBCATEGORY_ITEM = "li.universGroup__CategoryLi-sc-6qd6g7-8.yUtRm"

# Subcategory link
SELECTOR_SUBCATEGORY_LINK = "a.universGroup__CategoryLink-sc-6qd6g7-9.iUtWKS"
