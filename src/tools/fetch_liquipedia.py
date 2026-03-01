#!/usr/bin/env python3
"""
Parser for Dota 2 item descriptions from Liquipedia.
Exports structured item data (name, description, category, stats) to JSON.

Data Source: Liquipedia Dota 2 (https://liquipedia.net/dota2/)
License: CC-BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/)
API Terms: https://liquipedia.net/api-terms-of-use
"""

import sys

# Disable .pyc cache to avoid stale bytecode issues after refactoring
sys.dont_write_bytecode = True

import argparse
import json
import logging
import re
import time
from enum import Enum
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class CacheMode(Enum):
    """Cache behavior modes."""

    NORMAL = "normal"  # Use cache if exists, fetch if missing
    CACHE_ONLY = "cache"  # Only use cache, skip missing items
    FORCE = "force"  # Ignore cache, always fetch
    FETCH_ONLY = "fetch"  # Only fetch and cache, don't parse


# Configuration (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output"
LIQUIPEDIA_PATH = PROJECT_ROOT / "liquipedia_parsed"
CACHE_PATH = LIQUIPEDIA_PATH / "cache"

# Request settings (per Liquipedia API Terms: parse action = 1 req / 30 sec)
REQUEST_DELAY = 30.0  # seconds between parse API requests
MAX_RETRIES = 5  # number of retry attempts before crashing
RETRY_DELAY = 60.0  # initial delay on 429 error (doubles each attempt)

# Parsing settings
MIN_TEXT_LENGTH_SHORT = 3  # minimum text length for additional_info items
MIN_TEXT_LENGTH = 5  # minimum text length for ability details/misc

# Required headers per Liquipedia API Terms of Use
# Must have custom User-Agent with project name and contact
HEADERS = {
    "User-Agent": "Dota2ItemEfficiencyAnalysis/1.0 (xcemaxx@gmail.com)",
    "Accept-Encoding": "gzip",
}

# MediaWiki API endpoint
API_URL = "https://liquipedia.net/dota2/api.php"

# Reusable session for connection pooling
session = requests.Session()
session.headers.update(HEADERS)

# Item categories from Liquipedia Portal:Items
ITEM_CATEGORIES = {
    # Basic Items
    "Consumables": [
        "Aghanim's Shard",
        "Blood Grenade",
        "Bottle",
        "Clarity",
        "Dust of Appearance",
        "Enchanted Mango",
        "Faerie Fire",
        "Healing Salve",
        "Observer Ward",
        "Sentry Ward",
        "Smoke of Deceit",
        "Tango",
        "Town Portal Scroll",
    ],
    "Attributes": [
        "Band of Elvenskin",
        "Belt of Strength",
        "Blade of Alacrity",
        "Circlet",
        "Crown",
        "Diadem",
        "Gauntlets of Strength",
        "Iron Branch",
        "Mantle of Intelligence",
        "Ogre Axe",
        "Robe of the Magi",
        "Slippers of Agility",
        "Staff of Wizardry",
    ],
    "Equipment": [
        "Blades of Attack",
        "Blitz Knuckles",
        "Broadsword",
        "Chainmail",
        "Claymore",
        "Gloves of Haste",
        "Helm of Iron Will",
        "Infused Raindrops",
        "Javelin",
        "Mithril Hammer",
        "Orb of Blight",
        "Orb of Frost",
        "Orb of Venom",
        "Quelling Blade",
        "Ring of Protection",
    ],
    "Miscellaneous": [
        "Blink Dagger",
        "Boots of Speed",
        "Cloak",
        "Fluffy Hat",
        "Gem of True Sight",
        "Ghost Scepter",
        "Magic Stick",
        "Morbid Mask",
        "Ring of Health",
        "Ring of Regen",
        "Sage's Mask",
        "Shadow Amulet",
        "Void Stone",
        "Voodoo Mask",
        "Wind Lace",
    ],
    "Secret Shop": [
        "Cornucopia",
        "Demon Edge",
        "Eaglesong",
        "Energy Booster",
        "Hyperstone",
        "Mystic Staff",
        "Platemail",
        "Point Booster",
        "Reaver",
        "Ring of Tarrasque",
        "Sacred Relic",
        "Talisman of Evasion",
        "Tiara of Selemene",
        "Ultimate Orb",
        "Vitality Booster",
    ],
    # Upgraded Items
    "Accessories": [
        "Boots of Travel",
        "Bracer",
        "Falcon Blade",
        "Hand of Midas",
        "Magic Wand",
        "Mask of Madness",
        "Moon Shard",
        "Null Talisman",
        "Oblivion Staff",
        "Orb of Corrosion",
        "Perseverance",
        "Phase Boots",
        "Power Treads",
        "Soul Booster",
        "Soul Ring",
        "Wraith Band",
    ],
    "Support": [
        "Arcane Boots",
        "Boots of Bearing",
        "Buckler",
        "Drum of Endurance",
        "Guardian Greaves",
        "Headdress",
        "Holy Locket",
        "Mekansm",
        "Pavise",
        "Pipe of Insight",
        "Ring of Basilius",
        "Solar Crest",
        "Spirit Vessel",
        "Tranquil Boots",
        "Urn of Shadows",
        "Vladmir's Offering",
    ],
    "Magical": [
        "Aether Lens",
        "Aghanim's Scepter",
        "Bloodstone",
        "Dagon",
        "Ethereal Blade",
        "Eul's Scepter of Divinity",
        "Force Staff",
        "Gleipnir",
        "Glimmer Cape",
        "Meteor Hammer",
        "Octarine Core",
        "Orchid Malevolence",
        "Refresher Orb",
        "Rod of Atos",
        "Scythe of Vyse",
        "Wind Waker",
    ],
    "Armor": [
        "Aeon Disk",
        "Armlet of Mordiggian",
        "Assault Cuirass",
        "Black King Bar",
        "Blade Mail",
        "Crimson Guard",
        "Eternal Shroud",
        "Eye of Skadi",
        "Heart of Tarrasque",
        "Helm of the Dominator",
        "Helm of the Overlord",
        "Linken's Sphere",
        "Lotus Orb",
        "Shiva's Guard",
        "Vanguard",
        "Veil of Discord",
    ],
    "Weapons": [
        "Abyssal Blade",
        "Battle Fury",
        "Bloodthorn",
        "Butterfly",
        "Crystalys",
        "Daedalus",
        "Desolator",
        "Diffusal Blade",
        "Disperser",
        "Divine Rapier",
        "Mage Slayer",
        "Monkey King Bar",
        "Nullifier",
        "Parasma",
        "Radiance",
        "Revenant's Brooch",
        "Shadow Blade",
        "Silver Edge",
        "Skull Basher",
        "Witch Blade",
    ],
    "Armaments": [
        "Arcane Blink",
        "Dragon Lance",
        "Echo Sabre",
        "Harpoon",
        "Heaven's Halberd",
        "Hurricane Pike",
        "Kaya",
        "Kaya and Sange",
        "Khanda",
        "Maelstrom",
        "Manta Style",
        "Mjollnir",
        "Overwhelming Blink",
        "Phylactery",
        "Sange",
        "Sange and Yasha",
        "Satanic",
        "Swift Blink",
        "Yasha",
        "Yasha and Kaya",
    ],
}


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Parse Dota 2 item descriptions from Liquipedia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage:
  %(prog)s --test                    Parse 4 test items
  %(prog)s --all                     Parse all items
  %(prog)s --items "Blade Mail" BKB  Parse specific items
  %(prog)s --all --cache-only        Only process cached items
  %(prog)s --all --force             Force re-fetch all items
  %(prog)s --all --fetch-only        Only update cache, no JSON output
        """,
    )

    # Item selection (mutually exclusive)
    items_group = parser.add_mutually_exclusive_group()
    items_group.add_argument(
        "--all", action="store_true", help="Parse all items from all categories"
    )
    items_group.add_argument(
        "--test",
        action="store_true",
        help="Parse test items (BKB, Blade Mail, Vlad, Spirit Vessel)",
    )
    items_group.add_argument(
        "--items", nargs="+", metavar="ITEM", help="Parse specific items by name"
    )

    # Cache behavior (mutually exclusive)
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--cache-only",
        action="store_true",
        help="Only process items that exist in cache, skip missing",
    )
    cache_group.add_argument(
        "--force", action="store_true", help="Ignore cache, always fetch from API and update cache"
    )
    cache_group.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch and update cache, do not parse to JSON",
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output JSON filename (default: auto-generated based on mode)",
    )

    # Utility options
    parser.add_argument(
        "--list-cached", action="store_true", help="List items that exist in cache and exit"
    )

    return parser


def ensure_cache_dir() -> None:
    """Create cache directory if it doesn't exist."""
    CACHE_PATH.mkdir(parents=True, exist_ok=True)


def get_cached_data(cache_key: str) -> str | None:
    """Load cached API response (JSON) if available."""
    ensure_cache_dir()
    cache_file = CACHE_PATH / f"{cache_key}.json"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    return None


def save_cached_data(data: str, cache_key: str) -> None:
    """Save API response (JSON) to cache."""
    ensure_cache_dir()
    cache_file = CACHE_PATH / f"{cache_key}.json"
    cache_file.write_text(data, encoding="utf-8")


def fetch_item_via_api(
    item_name: str, cache_key: str | None = None, cache_mode: CacheMode = CacheMode.NORMAL
) -> dict[str, Any] | None:
    """
    Fetch item data via MediaWiki API with parsed HTML content.

    Args:
        item_name: Name of the item to fetch
        cache_key: Key for caching
        cache_mode: Cache behavior mode
    """
    # Check cache first (unless forcing refresh)
    if cache_key and cache_mode != CacheMode.FORCE:
        cached = get_cached_data(cache_key)
        if cached:
            logger.debug("  [CACHE HIT] %s", cache_key)
            try:
                return json.loads(cached)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass
        elif cache_mode == CacheMode.CACHE_ONLY:
            logger.debug("  [CACHE MISS] %s - skipping (cache-only mode)", cache_key)
            return None

    # In cache-only mode, don't fetch if cache_key was not provided
    if cache_mode == CacheMode.CACHE_ONLY:
        return None

    # Convert item name to wiki title format
    title = item_name.replace(" ", "_")

    # Use parse API to get rendered HTML
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "text|categories|displaytitle",
        "disabletoc": "true",
    }

    logger.info("  [API] Fetching %s", item_name)

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.error("  [API ERROR] %s", data["error"].get("info", "Unknown error"))
                return None

            if cache_key:
                save_cached_data(json.dumps(data), cache_key)
                if cache_mode == CacheMode.FORCE:
                    logger.debug("  [CACHE UPDATE] %s", cache_key)

            # Delay after successful fetch (per Liquipedia API Terms: 1 req / 30 sec)
            time.sleep(REQUEST_DELAY)

            return data  # type: ignore[no-any-return]
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                retry_wait = RETRY_DELAY * (2**attempt)
                logger.warning(
                    "  [RETRY %d/%d] %s - waiting %ds", attempt + 1, MAX_RETRIES, e, retry_wait
                )
                time.sleep(retry_wait)
            else:
                raise RuntimeError(
                    f"Failed to fetch '{item_name}' after {MAX_RETRIES} attempts: {e}"
                ) from e

    return None  # unreachable, but keeps type checker happy


def item_name_to_cache_key(item_name: str) -> str:
    """Convert item name to safe cache filename."""
    return re.sub(r"[^\w\-]", "_", item_name.lower())


# ---------------------------------------------------------------------------
# Parsing helpers — each extracts one section from a Liquipedia item page
# ---------------------------------------------------------------------------


def _parse_infobox(
    infobox: Tag,
) -> tuple[int | None, dict[str, float], list[dict[str, str]]]:
    """Extract cost, bonus stats, and active ability names from item infobox.

    Returns:
        (cost, stats_dict, abilities_list)
    """
    cost: int | None = None
    stats: dict[str, float] = {}
    abilities: list[dict[str, str]] = []

    # Extract cost
    for th in infobox.find_all("th"):
        th_text = th.get_text(strip=True)
        if "Cost" in th_text:
            row = th.find_parent("tr")
            if row:
                for td in row.find_all("td"):
                    cost_text = td.get_text(strip=True)
                    cost_match = re.search(r"(\d+)", cost_text.replace(",", ""))
                    if cost_match:
                        cost = int(cost_match.group(1))
                        break

    # Extract bonus stats
    for th in infobox.find_all("th"):
        if "Bonus" in th.get_text():
            row = th.find_parent("tr")
            if row:
                for td in row.find_all("td"):
                    td_html = str(td)
                    stat_patterns = re.findall(
                        r"([+-]?\d+(?:\.\d+)?)\s*<a[^>]*>([^<]+)</a>", td_html
                    )
                    for value_str, stat_name in stat_patterns:
                        try:
                            stats[stat_name.strip()] = float(value_str)
                        except ValueError:
                            pass

    # Extract active ability name
    for th in infobox.find_all("th"):
        if "Active" in th.get_text():
            row = th.find_parent("tr")
            if row:
                ability_td = row.find("td")
                if ability_td:
                    ability_link = ability_td.find("a")
                    if ability_link:
                        ability_name = ability_link.get_text(strip=True)
                        abilities.append({"name": ability_name, "type": "active"})

    return cost, stats, abilities


def _parse_image(soup: BeautifulSoup) -> str | None:
    """Extract main item image URL."""
    img_cell = soup.find("td", id="itemmainimage")
    if img_cell:
        img = img_cell.find("img")
        if img and isinstance(img, Tag) and img.get("src"):
            src = str(img["src"])
            return "https://liquipedia.net" + src if src.startswith("/") else src
    return None


def _parse_description(soup: BeautifulSoup) -> str:
    """Extract first paragraph description."""
    first_p = soup.find("p")
    if first_p:
        desc_text = first_p.get_text(separator=" ", strip=True)
        desc_text = re.sub(r"\[\d+\]", "", desc_text)
        desc_text = re.sub(r"\s+", " ", desc_text)
        return desc_text
    return ""


def _parse_additional_info(soup: BeautifulSoup) -> list[str]:
    """Extract Additional Information section bullet points."""
    result: list[str] = []
    additional_header = soup.find("h2", id="Additional_Information")
    if not additional_header:
        return result

    parent = additional_header.find_parent("div", class_="mw-heading")
    if not parent:
        return result

    next_elem = parent.find_next_sibling()
    while next_elem:
        if next_elem.name == "div" and next_elem.find("h2"):
            break
        if next_elem.name == "ul":
            for li in next_elem.find_all("li"):
                text_parts: list[str] = []
                for child in li.children:
                    if hasattr(child, "name"):
                        if child.name not in ["ul", "li"]:
                            text_parts.append(child.get_text(separator=" ", strip=True))
                    else:
                        text_parts.append(str(child).strip())
                text = " ".join(text_parts).strip()
                text = re.sub(r"\s+", " ", text)
                if text and len(text) > MIN_TEXT_LENGTH_SHORT:
                    result.append(text)
        next_elem = next_elem.find_next_sibling()

    return result


def _extract_section_content(h6_elem: Tag, content_list: list[str]) -> None:
    """Extract list content from a spellcard section until next h6 or end."""
    parent = h6_elem.find_parent("div")
    next_elem = parent.find_next_sibling() if parent else None
    while next_elem:
        if next_elem.name == "div" and next_elem.find("h6"):
            break
        if next_elem.name == "ul":
            for li in next_elem.find_all("li", recursive=False):
                text = li.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text)
                if text and len(text) > MIN_TEXT_LENGTH:
                    content_list.append(text)
        next_elem = next_elem.find_next_sibling()


def _extract_status_effects(h6_elem: Tag, status_dict: dict[str, str]) -> None:
    """Extract status effects (modifier -> description) from spellcard section."""
    parent = h6_elem.find_parent("div")
    next_elem = parent.find_next_sibling() if parent else None
    while next_elem:
        if not isinstance(next_elem, Tag):
            next_elem = next_elem.find_next_sibling()
            continue
        if next_elem.name == "div" and next_elem.find("h6"):
            break
        for effect_div in next_elem.find_all("div", style=lambda s: s and "max-width:550px" in s):
            tt = effect_div.find("tt")
            desc_div = effect_div.find("div", style=lambda s: s and "font-size:90%" in s)
            if tt and desc_div:
                modifier_name = tt.get_text(strip=True)
                description = desc_div.get_text(strip=True)
                if modifier_name:
                    status_dict[modifier_name] = description
        next_elem = next_elem.find_next_sibling()


def _parse_spellcards(
    soup: BeautifulSoup, existing_abilities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Extract all abilities from spellcard-wrapper divs.

    Merges with existing_abilities (e.g. active ability names from infobox).
    """
    abilities = list(existing_abilities)

    spellcards = soup.find_all("div", class_="spellcard-wrapper")
    for spellcard in spellcards:
        ability_info: dict[str, Any] = {
            "name": "",
            "description": "",
            "cooldown": None,
            "mana_cost": None,
            "duration": None,
            "effects": [],
            "details": [],
            "status_effects": {},
            "misc": [],
        }

        # Ability name
        name_span = spellcard.find(
            "span", style=lambda s: s and "font-weight:bold" in s and "color:#FFF" in s
        )
        if name_span:
            ability_info["name"] = name_span.get_text(strip=True)

        # Ability description
        desc_div = spellcard.find(
            "div", style=lambda s: s and "vertical-align:top" in s and "font-size:85%" in s
        )
        if desc_div:
            ability_info["description"] = desc_div.get_text(strip=True)

        # Cooldown
        cooldown_icon = spellcard.find("a", title="Cooldown")
        if cooldown_icon:
            cooldown_cell = cooldown_icon.find_parent("div")
            if cooldown_cell:
                cooldown_value = cooldown_cell.find_next_sibling("div")
                if cooldown_value:
                    cd_match = re.search(r"(\d+)", cooldown_value.get_text())
                    if cd_match:
                        ability_info["cooldown"] = int(cd_match.group(1))

        # Mana cost
        mana_icon = spellcard.find("img", alt="Mana Cost")
        if mana_icon:
            mana_cell = mana_icon.find_parent("div")
            if mana_cell:
                mana_value = mana_cell.find_next_sibling("div")
                if mana_value:
                    mana_match = re.search(r"(\d+)", mana_value.get_text())
                    if mana_match:
                        ability_info["mana_cost"] = int(mana_match.group(1))

        # Duration
        duration_div = spellcard.find("span", string=re.compile(r"Duration"))
        if duration_div:
            duration_parent = duration_div.find_parent("div")
            if duration_parent:
                duration_text = duration_parent.get_text(strip=True)
                duration_match = re.search(r"Duration[:\s]+([0-9/]+)", duration_text)
                if duration_match:
                    ability_info["duration"] = duration_match.group(1)

        # Magic resistance bonus
        mr_div = spellcard.find("span", string=re.compile(r"Magic Resistance"))
        if mr_div:
            mr_parent = mr_div.find_parent("div")
            if mr_parent:
                mr_text = mr_parent.get_text(strip=True)
                mr_match = re.search(r"(\d+)%", mr_text)
                if mr_match:
                    ability_info["effects"].append(f"+{mr_match.group(1)}% Magic Resistance")

        # Find tabs-content that belongs to THIS spellcard
        tabs_content = spellcard.find("div", class_="tabs-content")
        if tabs_content:
            content1 = tabs_content.find("div", class_="content1")
            if content1:
                for li in content1.find_all("li"):
                    text = li.get_text(separator=" ", strip=True)
                    text = re.sub(r"\s+", " ", text)
                    if text and len(text) > MIN_TEXT_LENGTH:
                        ability_info["details"].append(text)

            content2 = tabs_content.find("div", class_="content2")
            if content2:
                for effect_div in content2.find_all(
                    "div", style=lambda s: s and "max-width:550px" in s
                ):
                    tt = effect_div.find("tt")
                    desc_div = effect_div.find("div", style=lambda s: s and "font-size:90%" in s)
                    if tt and desc_div:
                        modifier_name = tt.get_text(strip=True)
                        description = desc_div.get_text(strip=True)
                        if modifier_name:
                            ability_info["status_effects"][modifier_name] = description

            content3 = tabs_content.find("div", class_="content3")
            if content3:
                for li in content3.find_all("li"):
                    text = li.get_text(separator=" ", strip=True)
                    text = re.sub(r"\s+", " ", text)
                    if text and len(text) > MIN_TEXT_LENGTH:
                        ability_info["misc"].append(text)
        else:
            # No tabs — look for direct h6 headers (single-content abilities)
            h6_details = spellcard.find("h6", id="Details")
            if h6_details:
                _extract_section_content(h6_details, ability_info["details"])

            h6_status = spellcard.find("h6", id="Status_Effects")
            if h6_status:
                _extract_status_effects(h6_status, ability_info["status_effects"])

            h6_misc = spellcard.find("h6", id="Miscellaneous") or spellcard.find("h6", id="Misc")
            if h6_misc:
                _extract_section_content(h6_misc, ability_info["misc"])

        # Add or update ability
        if ability_info["name"]:
            found = False
            for i, ab in enumerate(abilities):
                if ab.get("name") == ability_info["name"]:
                    abilities[i].update(ability_info)
                    found = True
                    break
            if not found:
                abilities.append(ability_info)

    return abilities


def _parse_components(soup: BeautifulSoup, item_name: str) -> list[dict[str, Any]]:
    """Extract components from recipe section.

    Only extracts when current item is the result (first link in recipe section).
    """
    components: list[dict[str, Any]] = []
    recipe_section = soup.find("th", string=re.compile(r"^Recipe$"))
    if not recipe_section:
        return components

    recipe_row = recipe_section.find_parent("tr")
    if not recipe_row:
        return components

    next_row = recipe_row.find_next_sibling("tr")
    if not next_row or not isinstance(next_row, Tag):
        return components

    all_links = next_row.find_all("a", title=True)
    if not all_links:
        return components

    # Check if current item is the FIRST link (meaning it's the result)
    first_link_title = all_links[0].get("title", "")
    first_match = re.match(r"([^(]+)\s*\((\d+)\)", first_link_title)
    if not first_match or first_match.group(1).strip() != item_name:
        return components

    # Current item is the result — extract components (skip first)
    for link in all_links[1:]:
        title = link.get("title", "")
        comp_match = re.match(r"([^(]+)\s*\((\d+)\)", title)
        if comp_match:
            comp_name = comp_match.group(1).strip()
            comp_cost = int(comp_match.group(2))
            if comp_name != item_name:
                components.append({"name": comp_name, "cost": comp_cost})

    return components


def parse_item_page(html: str, item_name: str) -> dict[str, Any]:
    """Parse an item page from Liquipedia and extract structured data."""
    soup = BeautifulSoup(html, "html.parser")

    cost: int | None = None
    stats: dict[str, float] = {}
    abilities: list[dict[str, Any]] = []

    infobox = soup.find("table", class_="fo-nttax-infobox")
    if infobox and isinstance(infobox, Tag):
        cost, stats, abilities = _parse_infobox(infobox)

    abilities = _parse_spellcards(soup, abilities)

    return {
        "item": item_name,
        "group": get_item_category(item_name),
        "description": _parse_description(soup),
        "cost": cost,
        "stats": stats,
        "additional_info": _parse_additional_info(soup),
        "abilities": abilities,
        "components": _parse_components(soup, item_name),
        "image_url": _parse_image(soup),
    }


def get_item_category(item_name: str) -> str:
    """Get the category for an item."""
    for category, items in ITEM_CATEGORIES.items():
        if item_name in items:
            return category
    return "Unknown"


def parse_single_item(
    item_name: str, cache_mode: CacheMode = CacheMode.NORMAL
) -> dict[str, Any] | None:
    """
    Parse a single item from Liquipedia via API.

    Args:
        item_name: Name of the item
        cache_mode: Cache behavior mode

    Returns:
        Parsed item data, or None if skipped (cache-only mode)
    """
    cache_key = item_name_to_cache_key(item_name)

    api_data = fetch_item_via_api(item_name, cache_key, cache_mode)

    if api_data is None:
        if cache_mode == CacheMode.CACHE_ONLY:
            return None  # Skip this item
        return {
            "item": item_name,
            "group": get_item_category(item_name),
            "error": "Failed to fetch from API",
        }

    # Extract HTML content from API response
    try:
        html = api_data.get("parse", {}).get("text", {}).get("*", "")
        if not html:
            return {
                "item": item_name,
                "group": get_item_category(item_name),
                "error": "No HTML content in API response",
            }
        return parse_item_page(html, item_name)
    except (KeyError, AttributeError, TypeError) as e:
        return {
            "item": item_name,
            "group": get_item_category(item_name),
            "error": f"Parse error ({type(e).__name__}): {e}",
        }


TEST_ITEMS = ["Black King Bar", "Blade Mail", "Vladmir's Offering", "Spirit Vessel"]


def get_all_item_names() -> list[str]:
    """Get flat list of all item names from categories."""
    items: list[str] = []
    for category_items in ITEM_CATEGORIES.values():
        items.extend(category_items)
    return items


def get_cached_item_names() -> list[str]:
    """Get list of item names that exist in cache."""
    if not CACHE_PATH.exists():
        return []

    cached: list[str] = []
    for cache_file in CACHE_PATH.iterdir():
        if cache_file.suffix == ".json":
            cache_key = cache_file.stem
            for item_name in get_all_item_names():
                if item_name_to_cache_key(item_name) == cache_key:
                    cached.append(item_name)
                    break
    return cached


def run_parser(items: list[str], cache_mode: CacheMode, output_file: Path | None = None) -> None:
    """
    Main parser function.

    Args:
        items: List of item names to parse
        cache_mode: Cache behavior mode
        output_file: Output JSON filename relative to LIQUIPEDIA_PATH (None = don't save)
    """
    logger.info("=" * 70)
    logger.info("DOTA 2 ITEM DESCRIPTION PARSER (Liquipedia)")
    logger.info("Mode: %s", cache_mode.value)
    logger.info("Items: %d", len(items))
    logger.info("API delay: %ss between requests", REQUEST_DELAY)
    logger.info("=" * 70)

    LIQUIPEDIA_PATH.mkdir(parents=True, exist_ok=True)

    all_items: list[dict[str, Any]] = []
    skipped = 0

    for i, item_name in enumerate(items, 1):
        logger.info("\n[%d/%d] %s", i, len(items), item_name)
        logger.info("-" * 50)

        item_data = parse_single_item(item_name, cache_mode)

        if item_data is None:
            skipped += 1
            continue

        if cache_mode != CacheMode.FETCH_ONLY:
            all_items.append(item_data)
            logger.info("  Cost: %s", item_data.get("cost"))
            logger.info("  Stats: %s", item_data.get("stats"))
            logger.info("  Abilities: %d", len(item_data.get("abilities", [])))

    logger.info("\n" + "=" * 70)

    if cache_mode == CacheMode.FETCH_ONLY:
        logger.info("[DONE] Fetched %d items to cache", len(items) - skipped)
        if skipped:
            logger.info("[SKIPPED] %d items", skipped)
        return

    logger.info("[DONE] Parsed %d items", len(all_items))
    if skipped:
        logger.info("[SKIPPED] %d items (not in cache)", skipped)

    # Save results
    if output_file and all_items:
        output_path = LIQUIPEDIA_PATH / output_file
        output_path.write_text(
            json.dumps(all_items, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Saved to: %s", output_path)

    # Statistics
    errors = [item for item in all_items if "error" in item]
    if errors:
        logger.warning("%d items had errors:", len(errors))
        for item in errors:
            logger.warning("  - %s: %s", item["item"], item["error"])

    logger.info("=" * 70)


def main() -> None:
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = create_parser()
    args = parser.parse_args()

    # Handle --list-cached
    if args.list_cached:
        cached = get_cached_item_names()
        print(f"Cached items ({len(cached)}):")
        for item in sorted(cached):
            print(f"  - {item}")
        return

    # Determine cache mode
    if args.cache_only:
        cache_mode = CacheMode.CACHE_ONLY
    elif args.force:
        cache_mode = CacheMode.FORCE
    elif args.fetch_only:
        cache_mode = CacheMode.FETCH_ONLY
    else:
        cache_mode = CacheMode.NORMAL

    # Determine items to parse
    if args.all:
        items = get_all_item_names()
        default_output = Path("items_descriptions.json")
    elif args.test:
        items = TEST_ITEMS
        default_output = Path("items_test.json")
    elif args.items:
        items = args.items
        default_output = Path("items_custom.json")
    else:
        # Default: just BKB
        items = ["Black King Bar"]
        default_output = Path("bkb_test.json")

    # Determine output file
    output_file: Path | None = Path(args.output) if args.output else default_output
    if args.fetch_only:
        output_file = None  # Don't save JSON in fetch-only mode

    run_parser(items, cache_mode, output_file)


if __name__ == "__main__":
    main()
