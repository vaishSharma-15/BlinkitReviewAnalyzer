"""Phase 01 ingest: quick-commerce comparison discussions (Blinkit vs Zepto vs Instamart).

A targeted slice, not a separate site: pulls comparison-specific search terms from
Reddit and YouTube and tags every item qcomm_comparison, per spec §7 ("treat as a
targeted slice ... tag these items qcomm_comparison at ingest"). Reddit requires OAuth
credentials (praw); when absent, that half is skipped and documented, and the YouTube
half (yt-dlp + youtube-comment-downloader, no key required) still runs.

Usage:
    python -m src.ingest.qcomm_discussions --config config.yaml [--limit 50]
"""
import os
from typing import List

from dotenv import load_dotenv

from src.ingest.common import (
    append_records, base_arg_parser, load_config, setup_logging,
    total_count, window_start, write_manifest,
)
from src.ingest.reddit import build_client, comment_to_record, submission_to_record
from src.ingest.youtube import fetch_comments, search_videos
from src.schemas import RawRecord
from youtube_comment_downloader import YoutubeCommentDownloader

SOURCE = "qcomm_comparison"


def fetch_reddit(qcomm_cfg: dict, limit, cutoff, logger) -> List[RawRecord]:
    client = build_client()
    records: List[RawRecord] = []
    seen = set()

    def add(record):
        if record is None or record.id in seen or not record.text.strip():
            return
        record.id = f"qcomm_reddit_{record.id}"
        record.source = SOURCE
        record.meta["origin"] = "reddit"
        seen.add(record.id)
        records.append(record)

    for subreddit_name in qcomm_cfg["reddit_subreddits"]:
        subreddit = client.subreddit(subreddit_name)
        for term in qcomm_cfg["search_terms"]:
            for submission in subreddit.search(term, sort="new", time_filter="all", limit=50):
                if limit is not None and len(records) >= limit:
                    return records
                add(submission_to_record(submission, cutoff, logger))

                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list()[:30]:
                    if limit is not None and len(records) >= limit:
                        return records
                    add(comment_to_record(comment, submission, cutoff))

            logger.info("reddit subreddit=%s term=%s total=%d", subreddit_name, term, len(records))

    return records


def fetch_youtube(qcomm_cfg: dict, limit, cutoff, logger) -> List[RawRecord]:
    downloader = YoutubeCommentDownloader()
    records: List[RawRecord] = []
    seen = set()

    max_videos = qcomm_cfg.get("youtube_max_videos_per_term", 15)
    max_comments = qcomm_cfg.get("youtube_max_comments_per_video", 100)

    for term in qcomm_cfg.get("youtube_search_terms", []):
        video_ids = search_videos(term, max_videos, logger)
        for video_id in video_ids:
            if limit is not None and len(records) >= limit:
                return records
            comments = fetch_comments(downloader, video_id, max_comments, cutoff, logger)
            for comment in comments:
                qid = f"qcomm_{comment.id}"
                if qid in seen:
                    continue
                if limit is not None and len(records) >= limit:
                    return records
                comment.id = qid
                comment.source = SOURCE
                comment.meta["origin"] = "youtube"
                seen.add(qid)
                records.append(comment)
            logger.info("youtube term=%s video=%s total=%d", term, video_id, len(records))

    return records


def main():
    load_dotenv()
    parser = base_arg_parser("Ingest quick-commerce comparison discussions (Blinkit vs Zepto/Instamart)")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    qcomm_cfg = config["qcomm_discussions"]
    cutoff = window_start(config["window_months"])

    records: List[RawRecord] = []
    reddit_blocked = not os.environ.get("REDDIT_CLIENT_ID") or not os.environ.get("REDDIT_CLIENT_SECRET")

    if reddit_blocked:
        logger.warning("REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET not set — skipping the Reddit half.")
    else:
        logger.info("starting reddit fetch: subreddits=%d limit=%s", len(qcomm_cfg["reddit_subreddits"]), args.limit)
        records.extend(fetch_reddit(qcomm_cfg, args.limit, cutoff, logger))

    remaining_limit = None if args.limit is None else max(args.limit - len(records), 0)
    if remaining_limit is None or remaining_limit > 0:
        logger.info("starting youtube fetch: terms=%d limit=%s", len(qcomm_cfg.get("youtube_search_terms", [])), remaining_limit)
        records.extend(fetch_youtube(qcomm_cfg, remaining_limit, cutoff, logger))

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, qcomm_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
        "reddit_blocked": reddit_blocked,
        "note": "Reddit half requires REDDIT_CLIENT_ID/SECRET; YouTube half uses yt-dlp + youtube-comment-downloader (no key required).",
    })


if __name__ == "__main__":
    main()
