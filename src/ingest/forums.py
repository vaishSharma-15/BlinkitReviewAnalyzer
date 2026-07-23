"""Phase 01 ingest: forum / community content (Quora, MouthShut) mentioning Blinkit.

Fetches with httpx, parses with selectolax, respects robots.txt, and rate-limits to
~1 req/sec per config. Site markup changes over time — if a site's selectors stop
matching, this script logs zero results for that site rather than raising, and the
gap must be documented in README.md per the source-coverage requirement.

Usage:
    python -m src.ingest.forums --config config.yaml [--limit 50]
"""
import time
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from typing import List

import httpx
from selectolax.parser import HTMLParser

from src.ingest.common import (
    append_records, base_arg_parser, is_probably_spam, load_config,
    setup_logging, total_count, window_start, write_manifest,
)
from src.schemas import RawRecord

SOURCE = "forum"
USER_AGENT = "blinkit-discovery-engine/0.1 (research; contact via repo)"


def robots_allowed(url: str, logger) -> bool:
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    try:
        parser.set_url(robots_url)
        parser.read()
        return parser.can_fetch(USER_AGENT, url)
    except Exception as exc:
        logger.warning("robots.txt check failed for %s: %s — skipping site to be safe", robots_url, exc)
        return False


def fetch_site_results(client: httpx.Client, site_cfg: dict, term: str, cutoff, logger, rate_limit: float) -> List[RawRecord]:
    search_url = site_cfg["search_url_template"].format(query=urllib.parse.quote(term))

    if not robots_allowed(search_url, logger):
        logger.warning("robots.txt disallows %s — not scraping", search_url)
        return []

    time.sleep(rate_limit)
    try:
        response = client.get(search_url, headers={"User-Agent": USER_AGENT}, timeout=15.0)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("request failed for %s: %s", search_url, exc)
        return []

    tree = HTMLParser(response.text)
    records: List[RawRecord] = []
    now = datetime.now(timezone.utc)

    for node in tree.css("a"):
        href = node.attributes.get("href")
        text = node.text(strip=True)
        if not href or not text or is_probably_spam(text):
            continue
        if len(text) < 15:
            continue
        absolute_url = urllib.parse.urljoin(search_url, href)
        item_id = f"forum_{site_cfg['name']}_{abs(hash(absolute_url))}"
        records.append(RawRecord(
            id=item_id,
            source=SOURCE,
            url=absolute_url,
            date=now.isoformat(),
            text=text,
            rating=None,
            meta={"site": site_cfg["name"], "search_term": term, "date_confidence": "fetch_time_only"},
        ))

    return records


def fetch(forums_cfg: dict, limit, cutoff, logger) -> List[RawRecord]:
    records: List[RawRecord] = []
    seen = set()
    rate_limit = forums_cfg.get("rate_limit_seconds", 1.0)

    with httpx.Client(follow_redirects=True) as client:
        for site_cfg in forums_cfg["sites"]:
            for term in forums_cfg["search_terms"]:
                if limit is not None and len(records) >= limit:
                    return records
                results = fetch_site_results(client, site_cfg, term, cutoff, logger, rate_limit)
                for record in results:
                    if record.id in seen:
                        continue
                    seen.add(record.id)
                    records.append(record)
                    if limit is not None and len(records) >= limit:
                        break
                logger.info("site=%s term=%s total=%d", site_cfg["name"], term, len(records))

    return records


def main():
    parser = base_arg_parser("Ingest forum/community content mentioning Blinkit")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    forums_cfg = config["forums"]
    cutoff = window_start(config["window_months"])

    logger.info("starting fetch: sites=%d limit=%s", len(forums_cfg["sites"]), args.limit)

    records = fetch(forums_cfg, args.limit, cutoff, logger)

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, forums_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
        "note": "search-results scraping; no reliable post date available at listing level — verify per-item selectors before a full run",
    })


if __name__ == "__main__":
    main()
