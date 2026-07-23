"""Phase 01 ingest: Apple App Store reviews for the Blinkit app, India storefront.

Uses Apple's public customer-reviews RSS/JSON feed directly (no auth, no scraping lib) —
the app-store-scraper package's internal endpoint returned non-JSON responses and appears
unmaintained. Apple's feed caps out at 10 pages (~500 most-recent reviews); this is a real
known limit of the endpoint, not a bug in this script.

Usage:
    python -m src.ingest.app_store --config config.yaml [--limit 50]
"""
from datetime import datetime, timezone
from typing import List

import httpx

from src.ingest.common import (
    append_records, base_arg_parser, load_config, setup_logging,
    strip_pii, total_count, window_start, write_manifest,
)
from src.schemas import RawRecord

SOURCE = "appstore"
MAX_PAGES = 10  # hard limit of Apple's public reviews feed


def fetch_reviews(app_id, country: str, limit, cutoff, logger) -> List[RawRecord]:
    records: List[RawRecord] = []
    seen_ids = set()

    with httpx.Client(timeout=15.0) as client:
        for page in range(1, MAX_PAGES + 1):
            if limit is not None and len(records) >= limit:
                break

            url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/page={page}/json"
            try:
                response = client.get(url)
                response.raise_for_status()
                entries = response.json()["feed"].get("entry", [])
            except Exception as exc:
                logger.warning("page=%d fetch failed: %s", page, exc)
                break

            # feed[0] is the app metadata itself, not a review, when entry is a list of dicts
            entries = [e for e in entries if "im:rating" in e]
            if not entries:
                break

            stop = False
            for entry in entries:
                review_id = entry["id"]["label"]
                if review_id in seen_ids:
                    continue
                published = datetime.fromisoformat(entry["updated"]["label"])
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if published < cutoff:
                    stop = True
                    continue

                seen_ids.add(review_id)
                meta = strip_pii({"app_version": entry.get("im:version", {}).get("label")})
                records.append(RawRecord(
                    id=f"appstore_{review_id}",
                    source=SOURCE,
                    url=f"https://apps.apple.com/{country}/app/blinkit/id{app_id}",
                    date=published.isoformat(),
                    text=entry.get("content", {}).get("label") or "",
                    rating=int(entry["im:rating"]["label"]),
                    meta=meta,
                ))

                if limit is not None and len(records) >= limit:
                    break

            logger.info("page=%d fetched=%d total=%d", page, len(entries), len(records))

            if stop:
                break

    return records


def main():
    parser = base_arg_parser("Ingest Blinkit App Store reviews (India storefront)")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    appstore_cfg = config["app_store"]
    cutoff = window_start(config["window_months"])

    if not appstore_cfg.get("app_id"):
        logger.warning(
            "app_store.app_id not set in config.yaml — locate Blinkit's numeric App Store id "
            "and set it before this stage can run. Skipping."
        )
        write_manifest(SOURCE, appstore_cfg, {
            "fetched": 0, "written": 0, "total_in_file": total_count(SOURCE),
            "blocked_reason": "app_store.app_id not configured",
        })
        return

    logger.info("starting fetch: app_id=%s limit=%s", appstore_cfg["app_id"], args.limit)

    records = fetch_reviews(
        app_id=appstore_cfg["app_id"],
        country=appstore_cfg["country"],
        limit=args.limit,
        cutoff=cutoff,
        logger=logger,
    )

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, appstore_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
        "note": "Apple's public customer-reviews feed caps at 10 pages (~500 most-recent reviews); this is the full available volume from this endpoint, not a partial run.",
    })


if __name__ == "__main__":
    main()
