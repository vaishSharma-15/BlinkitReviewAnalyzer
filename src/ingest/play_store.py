"""Phase 01 ingest: Google Play Store reviews for the Blinkit app.

Usage:
    python -m src.ingest.play_store --config config.yaml [--limit 50]
"""
from datetime import datetime, timezone
from typing import List

from google_play_scraper import Sort, reviews

from src.ingest.common import (
    append_records, base_arg_parser, load_config, setup_logging,
    strip_pii, total_count, window_start, write_manifest,
)
from src.schemas import RawRecord

SOURCE = "play"
SORTS = [Sort.NEWEST, Sort.MOST_RELEVANT]
SCORES = [1, 2, 3, 4, 5]
PAGE_SIZE = 200


def fetch_reviews(app_id: str, country: str, lang: str, target_count: int, limit: int, cutoff: datetime, logger):
    records: List[RawRecord] = []
    seen_ids = set()

    # Cap per (sort, score) bucket so a single heavily-populated bucket (e.g. 1-star
    # reviews, which can run into the hundreds of thousands) can't starve the others —
    # without this cap the loop never reaches the remaining score buckets.
    per_bucket_cap = max(target_count, 5000)

    for sort in SORTS:
        for score in SCORES:
            if limit is not None and len(records) >= limit:
                return records

            continuation_token = None
            fetched_this_bucket = 0
            while fetched_this_bucket < per_bucket_cap:
                result, continuation_token = reviews(
                    app_id,
                    lang=lang,
                    country=country,
                    sort=sort,
                    count=PAGE_SIZE,
                    filter_score_with=score,
                    continuation_token=continuation_token,
                )
                if not result:
                    break

                stop_bucket = False
                for entry in result:
                    if fetched_this_bucket >= per_bucket_cap:
                        break

                    review_id = entry["reviewId"]
                    if review_id in seen_ids:
                        continue
                    review_date = entry["at"].replace(tzinfo=timezone.utc)
                    if review_date < cutoff:
                        stop_bucket = True
                        continue

                    seen_ids.add(review_id)
                    meta = strip_pii({
                        "app_version": entry.get("reviewCreatedVersion"),
                        "thumbs_up": entry.get("thumbsUpCount"),
                        "sort": str(sort),
                    })
                    records.append(RawRecord(
                        id=f"play_{review_id}",
                        source=SOURCE,
                        url=f"https://play.google.com/store/apps/details?id={app_id}&reviewId={review_id}",
                        date=review_date.isoformat(),
                        text=entry.get("content") or "",
                        rating=entry.get("score"),
                        meta=meta,
                    ))
                    fetched_this_bucket += 1

                    if limit is not None and len(records) >= limit:
                        return records

                logger.info(
                    "sort=%s score=%s fetched=%d total=%d",
                    sort, score, fetched_this_bucket, len(records),
                )

                if stop_bucket or continuation_token is None or not continuation_token.token:
                    break

    return records


def main():
    parser = base_arg_parser("Ingest Blinkit Play Store reviews")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    play_cfg = config["play_store"]
    cutoff = window_start(config["window_months"])

    logger.info("starting fetch: app_id=%s window_months=%s limit=%s", play_cfg["app_id"], config["window_months"], args.limit)

    records = fetch_reviews(
        app_id=play_cfg["app_id"],
        country=play_cfg["country"],
        lang=play_cfg["lang"],
        target_count=play_cfg["target_count"],
        limit=args.limit,
        cutoff=cutoff,
        logger=logger,
    )

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, play_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
    })


if __name__ == "__main__":
    main()
