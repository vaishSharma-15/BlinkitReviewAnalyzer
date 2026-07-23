"""Phase 01 ingest: YouTube comments on Blinkit-related videos (social media conversations).

No YOUTUBE_API_KEY was available, so this uses unauthenticated tools instead of the
official Data API v3 (a deliberate substitution from the decided tech stack, approved
by the user): yt-dlp for video search, youtube-comment-downloader for comment scraping.
Both hit YouTube's public pages directly rather than a stable API, so they are more
fragile to YouTube markup/behaviour changes than an official API integration would be.

Usage:
    python -m src.ingest.youtube --config config.yaml [--limit 50]
"""
from datetime import datetime, timezone
from typing import List

import yt_dlp
from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader

from src.ingest.common import (
    append_records, base_arg_parser, load_config, setup_logging,
    strip_pii, total_count, window_start, write_manifest,
)
from src.schemas import RawRecord

SOURCE = "youtube"


def search_videos(term: str, max_results: int, logger) -> List[str]:
    ydl_opts = {"quiet": True, "extract_flat": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{term}", download=False)
    except Exception as exc:
        logger.warning("search failed for term=%r: %s", term, exc)
        return []
    return [entry["id"] for entry in info.get("entries", []) if entry.get("id")]


def fetch_comments(downloader: YoutubeCommentDownloader, video_id: str, max_comments: int, cutoff, logger) -> List[RawRecord]:
    records: List[RawRecord] = []
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        generator = downloader.get_comments_from_url(url, sort_by=SORT_BY_RECENT)
        for comment in generator:
            if len(records) >= max_comments:
                break
            timestamp = comment.get("time_parsed")
            if timestamp is None:
                continue
            published = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            if published < cutoff:
                break  # SORT_BY_RECENT means once we're past cutoff, the rest are older
            meta = strip_pii({"video_id": video_id, "likes": comment.get("votes")})
            records.append(RawRecord(
                id=f"youtube_{comment['cid']}",
                source=SOURCE,
                url=f"{url}&lc={comment['cid']}",
                date=published.isoformat(),
                text=comment.get("text") or "",
                rating=None,
                meta=meta,
            ))
    except Exception as exc:
        logger.warning("comment fetch failed for video=%s: %s", video_id, exc)

    return records


def fetch(youtube_cfg: dict, limit, cutoff, logger) -> List[RawRecord]:
    downloader = YoutubeCommentDownloader()
    records: List[RawRecord] = []
    seen = set()

    for term in youtube_cfg["search_terms"]:
        video_ids = search_videos(term, youtube_cfg["max_videos_per_term"], logger)
        for video_id in video_ids:
            if limit is not None and len(records) >= limit:
                return records
            comments = fetch_comments(downloader, video_id, youtube_cfg["max_comments_per_video"], cutoff, logger)
            for comment in comments:
                if comment.id in seen:
                    continue
                if limit is not None and len(records) >= limit:
                    return records
                seen.add(comment.id)
                records.append(comment)
            logger.info("term=%s video=%s total=%d", term, video_id, len(records))

    return records


def main():
    parser = base_arg_parser("Ingest YouTube comments on Blinkit-related videos")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging(SOURCE)

    youtube_cfg = config["youtube"]
    cutoff = window_start(config["window_months"])

    logger.info("starting fetch: search_terms=%d limit=%s", len(youtube_cfg["search_terms"]), args.limit)

    records = fetch(youtube_cfg, args.limit, cutoff, logger)

    written = append_records(SOURCE, records)
    grand_total = total_count(SOURCE)

    logger.info("fetched=%d new=%d total_in_file=%d", len(records), written, grand_total)

    write_manifest(SOURCE, youtube_cfg, {
        "fetched": len(records),
        "written": written,
        "total_in_file": grand_total,
        "cutoff": cutoff.isoformat(),
        "note": "fetched via yt-dlp search + youtube-comment-downloader (no YOUTUBE_API_KEY available), not the official Data API v3",
    })


if __name__ == "__main__":
    main()
