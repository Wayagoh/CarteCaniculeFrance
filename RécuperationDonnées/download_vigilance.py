"""
download_vigilance.py
---------------------
Download Météo-France weather vigilance JSON files from the open data bucket.

Source : https://console.object.files.data.gouv.fr/browser/meteofrance/data/vigilance/metropole/
Index  : vigilance-hexagone-tree.json  (tree of all available files)
License: Licence Ouverte Etalab — source: Météo-France
"""

import json
import logging
import time
from datetime import date
from pathlib import Path

import requests

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

# BASE_URL   = r"https://console.object.files.data.gouv.fr/browser/meteofrance/data%2Fvigilance%2Fmetropole%2F"
# CARTE_FILE = "CDP_CARTE_EXTERNE.json"     # vigilance levels by department
# TEXTE_FILE = "CDP_TEXTES_VIGILANCE.json"  # meteorologist bulletins (text)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

BASE_URL   = "https://object.files.data.gouv.fr/meteofrance/data/vigilance/metropole"
CARTE_FILE = "CDP_CARTE_EXTERNE.json"
TEXTE_FILE = "CDP_TEXTES_VIGILANCE.json"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def load_tree(tree_path: Path) -> dict:
    """Load the file index JSON."""
    with open(tree_path, encoding="utf-8") as f:
        return json.load(f)


def in_date_range(year: str, month: str, start: date, end: date) -> bool:
    """Return True if (year, month) falls within [start, end]."""
    pivot = date(int(year), int(month), 1)
    return date(start.year, start.month, 1) <= pivot <= date(end.year, end.month, 1)


def last_emission(emissions: dict, target_file: str) -> str | None:
    """
    Return the timestamp (HHMMSS) of the last emission of the day
    that contains target_file, or None if absent.
    """
    candidates = [ts for ts, files in emissions.items() if target_file in files]
    return max(candidates) if candidates else None


def build_url(year: str, month: str, day: str, timestamp: str, filename: str) -> str:
    """Assemble the full download URL for one file."""
    return f"{BASE_URL}/{year}/{month}/{day}/{timestamp}/{filename}"


def download_file(url: str, dest: Path, retry: int = 3, delay: float = 1.0) -> bool:
    """
    Download url to dest. Skip if dest already exists.
    Retry up to `retry` times on network error.
    Returns True on success, False on failure.
    """
    if dest.exists():
        log.debug("skip  %s (already downloaded)", dest.name)
        return True

    for attempt in range(1, retry + 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(response.content)
            return True
        except requests.RequestException as exc:
            log.warning("attempt %d/%d failed for %s: %s", attempt, retry, url, exc)
            if attempt < retry:
                time.sleep(delay)

    return False


# ─── CORE ─────────────────────────────────────────────────────────────────────

def download_vigilance(
    tree_path: Path,
    output_dir: Path,
    start: date,
    end: date,
    download_carte: bool = True,
    download_texte: bool = False,
) -> dict:
    """
    Download the last daily emission for each target file, for every day
    in [start, end].

    Parameters
    ----------
    tree_path       : path to the vigilance-hexagone-tree.json index
    output_dir      : root folder where files will be saved
    start / end     : inclusive date range
    download_carte  : download CDP_CARTE_EXTERNE.json  (vigilance map data)
    download_texte  : download CDP_TEXTES_VIGILANCE.json (bulletin text)

    Returns
    -------
    dict with keys "ok", "skipped", "missing", "errors"
    """
    tree = load_tree(tree_path)

    targets = []
    if download_carte:
        targets.append(CARTE_FILE)
    if download_texte:
        targets.append(TEXTE_FILE)

    if not targets:
        log.error("No target file selected. Enable download_carte or download_texte.")
        return {}

    stats = {"ok": 0, "skipped": 0, "missing": 0, "errors": 0}

    for year, months in tree.items():
        for month, days in months.items():

            if not in_date_range(year, month, start, end):
                continue

            for day, emissions in days.items():

                current_day = date(int(year), int(month), int(day))
                if not (start <= current_day <= end):
                    continue

                for target_file in targets:

                    timestamp = last_emission(emissions, target_file)

                    if timestamp is None:
                        log.debug("missing  %s-%s-%s  %s", year, month, day, target_file)
                        stats["missing"] += 1
                        continue

                    url  = build_url(year, month, day, timestamp, target_file)
                    dest = output_dir / year / month / day / f"{timestamp}_{target_file}"

                    if dest.exists():
                        log.debug("skip  %s-%s-%s  %s", year, month, day, target_file)
                        stats["skipped"] += 1
                        continue

                    success = download_file(url, dest)

                    if success:
                        log.info("ok    %s-%s-%s  %s  [%s]", year, month, day, timestamp, target_file)
                        stats["ok"] += 1
                    else:
                        log.error("error %s-%s-%s  %s", year, month, day, target_file)
                        stats["errors"] += 1

    return stats


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

def main():

    # ── Configuration ─────────────────────────────────────────────────────────
    TREE_PATH      = Path("data_vigilance_vigilance-hexagone-tree.json")
    OUTPUT_DIR     = Path("vigilance_data")
    START_DATE     = date(2023, 1, 1)
    END_DATE       = date(2025, 12, 31)
    DOWNLOAD_CARTE = True   # CDP_CARTE_EXTERNE.json  — vigilance levels
    DOWNLOAD_TEXTE = False  # CDP_TEXTES_VIGILANCE.json — bulletin text
    # ──────────────────────────────────────────────────────────────────────────

    log.info("Starting download — %s → %s", START_DATE, END_DATE)
    log.info("Output directory : %s", OUTPUT_DIR.resolve())

    stats = download_vigilance(
        tree_path=TREE_PATH,
        output_dir=OUTPUT_DIR,
        start=START_DATE,
        end=END_DATE,
        download_carte=DOWNLOAD_CARTE,
        download_texte=DOWNLOAD_TEXTE,
    )

    log.info(
        "Done — %d downloaded, %d skipped, %d missing, %d errors",
        stats.get("ok", 0),
        stats.get("skipped", 0),
        stats.get("missing", 0),
        stats.get("errors", 0),
    )


if __name__ == "__main__":
    main()