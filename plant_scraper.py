"""Scrape plant label data from NC State Plant Toolbox pages."""

import re
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

PLANT_TOOLBOX_HOST = "plants.ces.ncsu.edu"
PLANT_TOOLBOX_PATH = "/plants/"

CSV_COLUMNS = [
    "Common Name",
    "Scientific Name",
    "Light",
    "Water",
    "Soil",
    "pH",
    "Source URL",
]


def normalize_url(raw_url: str) -> str:
    """Validate and normalize a Plant Toolbox plant page URL."""
    url = raw_url.strip()
    if not url:
        raise ValueError("Empty URL.")

    parsed = urlparse(url)
    if parsed.netloc != PLANT_TOOLBOX_HOST:
        raise ValueError(f"URL must be on {PLANT_TOOLBOX_HOST}: {url}")

    path = parsed.path.rstrip("/") + "/"
    if not path.startswith(PLANT_TOOLBOX_PATH) or path == f"{PLANT_TOOLBOX_PATH}":
        raise ValueError(f"URL must point to a plant page under {PLANT_TOOLBOX_PATH}: {url}")

    return f"https://{PLANT_TOOLBOX_HOST}{path}"


def parse_urls(url_input: str) -> list[str]:
    """Split URLs on commas or new lines and return normalized unique URLs."""
    normalized_input = url_input.replace("\n", ",")
    parts = [part.strip() for part in normalized_input.split(",")]
    urls = []
    seen = set()

    for part in parts:
        if not part:
            continue
        url = normalize_url(part)
        if url not in seen:
            seen.add(url)
            urls.append(url)

    if not urls:
        raise ValueError("Enter at least one Plant Toolbox URL.")

    return urls


def get_detail_value(soup: BeautifulSoup, label: str) -> str:
    """Read a care attribute from a Plant Toolbox detail list."""
    dt_tag = soup.find("dt", string=label)
    if not dt_tag:
        return "Not found"

    span = dt_tag.find_next("span", class_="detail_display_attribute")
    return span.get_text(strip=True) if span else "Not found"


def scrape_plant(url: str) -> dict:
    """Scrape label fields from one Plant Toolbox plant page."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {
            "Common Name": "Error",
            "Scientific Name": "Error",
            "Light": f"Failed to fetch: {exc}",
            "Water": "",
            "Soil": "",
            "pH": "",
            "Source URL": url,
        }

    soup = BeautifulSoup(response.content, "html.parser")

    h1 = soup.find("h1")
    scientific_name = ""
    if h1:
        scientific_name = re.sub(r"Play pronunciation$", "", h1.get_text(strip=True)).strip()

    common_names_tag = soup.find("ul", id="common_names")
    common_name = "Not found"
    if common_names_tag:
        first_common = common_names_tag.find("li")
        if first_common:
            common_name = first_common.get_text(strip=True)
        else:
            names = [text for text in common_names_tag.stripped_strings if text]
            common_name = names[0] if names else "Not found"

    return {
        "Common Name": common_name,
        "Scientific Name": scientific_name or "Not found",
        "Light": get_detail_value(soup, "Light:"),
        "Water": get_detail_value(soup, "Soil Drainage:"),
        "Soil": get_detail_value(soup, "Soil Texture:"),
        "pH": get_detail_value(soup, "Soil pH:"),
        "Source URL": url,
    }


def build_label_rows(urls: list[str], labels_per_plant: int) -> pd.DataFrame:
    """Scrape each URL and duplicate rows for label printing."""
    rows = []

    for url in urls:
        plant_data = scrape_plant(url)
        for _ in range(labels_per_plant):
            rows.append(plant_data.copy())

    return pd.DataFrame(rows, columns=CSV_COLUMNS)
