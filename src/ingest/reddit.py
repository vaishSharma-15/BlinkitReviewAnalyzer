"""Phase 01 ingest: Reddit posts and comments mentioning Blinkit.

Usage:
    python -m src.ingest.reddit --config config.yaml [--limit 50]

Requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT in the environment (.env).
"""
import os
from datetime import datetime, timezone
from typing import List, Optional

import praw
from dotenv import load_dotenv

from src.ingest.common import (
    append_records, base_arg_parser, load_config, setup_logging,
    strip_pii, total_count, window_start, write_manifest,
)
from src.schemas import RawRecord

SOURCE = "reddit"


def build_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "blinkit-discovery-engine/0.1"),
        read_only=True,
    )


def submission_to_record(submission, cutoff, logger) -> Optional[RawRecord]:
    created = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
    if created < cutoff:
        return None
    text = (submission.title or "") + ("\n" + submission.selftext if submission.selftext else "")
    meta = strip_pii({"subreddit": str(submission.subreddit), "score": submission.score, "kind": "post"})
    return RawRecord(
        id=f"reddit_{submission.id}",
        source=SOURCE,
        url=f"https://reddit.com{submission.permalink}",
        date=created.isoformat(),
        text=text,
        rating=None,
        meta=meta,
    )


def comment_to_record(comment, submission, cutoff) -> Optional[RawRecord]:
    created = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
    if created < cutoff:
        return None
    meta = strip_pii({"subreddit": str(submission.subreddit), "score": comment.score, "kind": "comment"})
    return RawRecord(
        id=f"reddit_{comment.id}",
        source=SOURCE,
        url=f"https://reddit.com{comment.permalink}",
        date=created.isoformat(),
        text=comment.body or "",
        rating=None,
        meta=meta,
    )


def fetch(reddit_cfg: dict, limit, cutoff, logger) -> List[RawRecord]:
    client = build_client()
    records: List[RawRecord] = []
    seen = set()

    def add(record: Optional[RawRecord]):
        if record is None or record.id in seen:
            return False
        if not record.text.strip():
            return False
        seen.add(record.id)
        records.append(record)
        return True

    subreddits = reddit_cfg["subreddits"]
    search_terms = reddit_cfg["search_terms"]
    comment_limit = reddit_cfg["comment_limit_per_post"]

    for subreddit_name in subreddits:
        subreddit = client.subreddit(subreddit_name)
        for term in search_terms:
            for submission in subreddit.search(term, sort="new", time_filter="all", limit=100):
                if limit is not None and len(records) >= limit:
                    return records
                added = add(submission_to_record(submission, cutoff, logger))
                if not added and datetime.fromtimestamp(submission.created_utc, tz=timezone.utc) < cutoff:
                    continue

                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list()[:comment_limit]:
                    if limit is not None and len(records) >= limit:
                        return records
                    add(comment_to_record(comment, submission, cutoff))

                logger.info("subreddit=%s term=%s total=%d", subreddit_name, term, len(records))

    return records


def main():
    load_dotenv()
    parser = base_arg_parser("Ingest Reddit posts/comments mentioning Blinkit")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    reddit_cfg = config["reddit"]
    cutoff = window_start(config["window_months"])

    if not os.environ.get("REDDIT_CLIENT_ID") or not os.environ.get("REDDIT_CLIENT_SECRET"):
        logger.warning("REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET not set — cannot authenticate. Skipping.")
        write_manifest(SOURCE, reddit_cfg, {
            "fetched": 0, "written": 0, "total_in_file": total_count(SOURCE),
            "blocked_reason": "missing Reddit API credentials",
        })
        return

    logger.info("starting fetch: subreddits=%d limit=%s", len(reddit_cfg["subreddits"]), args.limit)

    records = fetch(reddit_cfg, args.limit, cutoff, logger)

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, reddit_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
    })


if __name__ == "__main__":
    main()
