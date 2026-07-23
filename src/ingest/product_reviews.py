"""Phase 01 ingest: product-detail-page reviews for a sample of non-core-category SKUs.

Tries Blinkit PDP reviews first; if blocked, falls back to Amazon India / Nykaa reviews
for an equivalent SKU and labels the record's source honestly as a proxy (per spec §7).

Usage:
    python -m src.ingest.product_reviews --config config.yaml [--limit 50]
"""
import time
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from selectolax.parser import HTMLParser

from src.ingest.common import (
    append_records, base_arg_parser, is_probably_spam, load_config,
    setup_logging, total_count, window_start, write_manifest,
)
from src.schemas import RawRecord

SOURCE = "product_review"
USER_AGENT = "blinkit-discovery-engine/0.1 (research; contact via repo)"


def try_blinkit_pdp(client: httpx.Client, query: str, logger) -> List[RawRecord]:
    """Blinkit does not expose a stable public PDP search/review endpoint for scraping
    without an authenticated session, so this attempt is expected to yield nothing —
    the caller falls back to a labelled proxy source, per the source-substitution rule."""
    search_url = f"https://blinkit.com/s/?q={urllib.parse.quote(query)}"
    try:
        response = client.get(search_url, headers={"User-Agent": USER_AGENT}, timeout=15.0)
        response.raise_for_status()
    except Exception as exc:
        logger.info("blinkit PDP fetch blocked for query=%r: %s", query, exc)
        return []

    tree = HTMLParser(response.text)
    review_nodes = tree.css("[data-review-text], .review-text")
    if not review_nodes:
        logger.info("blinkit PDP returned no parsable reviews for query=%r — falling back", query)
        return []

    records = []
    now = datetime.now(timezone.utc)
    for node in review_nodes:
        text = node.text(strip=True)
        if is_probably_spam(text):
            continue
        item_id = f"product_review_blinkit_{abs(hash(text))}"
        records.append(RawRecord(
            id=item_id, source=SOURCE, url=search_url, date=now.isoformat(),
            text=text, rating=None, meta={"category": None, "query": query, "vendor": "blinkit"},
        ))
    return records


def fallback_fetch(client: httpx.Client, vendor: str, category: str, query: str, cutoff, logger) -> List[RawRecord]:
    """Best-effort fallback search on Amazon India / Nykaa. Labels the record source
    honestly as a proxy since it is not a Blinkit-native review.

    NOTE: this hits the search-results page, not a product's review tab, so extracted
    text may include listing/navigation copy rather than genuine review text. Records
    are tagged meta.unverified_extraction=True so this must be spot-checked (or the
    selectors refined against a real product+review page) before being trusted in a
    full run.
    """
    if vendor == "amazon_in":
        search_url = f"https://www.amazon.in/s?k={urllib.parse.quote(query)}"
    elif vendor == "nykaa":
        search_url = f"https://www.nykaa.com/search/result/?q={urllib.parse.quote(query)}"
    else:
        return []

    try:
        response = client.get(search_url, headers={"User-Agent": USER_AGENT}, timeout=15.0)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("fallback vendor=%s blocked for query=%r: %s", vendor, query, exc)
        return []

    tree = HTMLParser(response.text)
    records = []
    now = datetime.now(timezone.utc)
    for node in tree.css("span, p"):
        text = node.text(strip=True)
        if not text or len(text) < 20 or len(text.split()) < 6 or is_probably_spam(text):
            continue
        item_id = f"product_review_{vendor}_{abs(hash(text))}"
        records.append(RawRecord(
            id=item_id, source=SOURCE, url=search_url, date=now.isoformat(),
            text=text, rating=None,
            meta={
                "category": category, "query": query, "vendor": vendor,
                "is_proxy_source": True, "unverified_extraction": True,
            },
        ))
    return records[:20]


def fetch(pr_cfg: dict, limit, cutoff, logger) -> List[RawRecord]:
    records: List[RawRecord] = []
    seen = set()
    rate_limit = pr_cfg.get("rate_limit_seconds", 1.0)

    with httpx.Client(follow_redirects=True) as client:
        for sku in pr_cfg["skus"]:
            if limit is not None and len(records) >= limit:
                return records

            time.sleep(rate_limit)
            native = try_blinkit_pdp(client, sku["query"], logger)
            batch = native
            if not batch:
                for vendor in pr_cfg.get("fallback_sources", []):
                    time.sleep(rate_limit)
                    batch = fallback_fetch(client, vendor, sku["category"], sku["query"], cutoff, logger)
                    if batch:
                        logger.info("category=%s using fallback vendor=%s (Blinkit PDP unscrapable)", sku["category"], vendor)
                        break

            for record in batch:
                if record.id in seen:
                    continue
                record.meta["category"] = sku["category"]
                seen.add(record.id)
                records.append(record)
                if limit is not None and len(records) >= limit:
                    break

            logger.info("category=%s query=%r total=%d", sku["category"], sku["query"], len(records))

    return records


def main():
    parser = base_arg_parser("Ingest product-review evidence for non-core category SKUs")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    pr_cfg = config["product_reviews"]
    cutoff = window_start(config["window_months"])

    logger.info("starting fetch: skus=%d limit=%s", len(pr_cfg["skus"]), args.limit)

    records = fetch(pr_cfg, args.limit, cutoff, logger)

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, pr_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
        "note": "Blinkit PDP reviews are not publicly scrapable without an authenticated session; "
                "records fall back to Amazon India / Nykaa and are tagged meta.vendor + meta.is_proxy_source honestly.",
    })


if __name__ == "__main__":
    main()
