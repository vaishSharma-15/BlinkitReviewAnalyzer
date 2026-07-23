"""Phase 08 (part 1) — Index: build a LanceDB vector index over evidence + themes.

Reads data/enriched/enriched.jsonl (evidence items, each independently citable — id, url,
source, quote) and data/themes/themes.jsonl (synthesized themes, if present), embeds text
with the same local model used throughout the pipeline (bge-small-en-v1.5, consistent
with src/normalize.py and src/cluster.py — no new embedding model introduced), and writes
a file-based LanceDB database under data/index/lancedb/. This is what app/rag_chatbot.py
queries at runtime so answers are grounded in retrieved evidence, not model priors, per
docs/ProblemStatement.md §7 (index and serve).

Two tables:
  - "evidence": one row per enriched record — the retrievable, citable unit.
  - "themes":   one row per synthesized theme (no vector; small enough to load whole,
    kept in the same DB for convenience and so the app has one place to query).

Idempotent: re-running overwrites both tables from scratch (this is a read-side rebuild,
not an appending ingest stage — safe since the DB is derived entirely from
data/enriched and data/themes, never a primary source of truth).

Usage:
    python -m src.index --config config.yaml [--enriched PATH] [--themes PATH]
"""
import json
from pathlib import Path
from typing import List

from src.ingest.common import base_arg_parser, setup_logging
from src.schemas import EnrichedRecord

REPO_ROOT = Path(__file__).resolve().parent.parent
ENRICHED_PATH = REPO_ROOT / "data" / "enriched" / "enriched.jsonl"
THEMES_PATH = REPO_ROOT / "data" / "themes" / "themes.jsonl"
INDEX_DIR = REPO_ROOT / "data" / "index" / "lancedb"
MANIFEST_PATH = REPO_ROOT / "data" / "index" / "manifest.json"

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_BATCH_SIZE = 64


def load_enriched(path: Path) -> List[EnrichedRecord]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(EnrichedRecord.model_validate_json(line))
    return records


def load_themes(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def embed_texts(texts: List[str]):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL_NAME)
    return model.encode(texts, batch_size=EMBED_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=True)


def main():
    parser = base_arg_parser("Build the LanceDB evidence + theme index for the RAG app")
    parser.add_argument("--enriched", default=None, help="Override enriched records path")
    parser.add_argument("--themes", default=None, help="Override themes path")
    args = parser.parse_args()
    logger = setup_logging("index")

    enriched_path = Path(args.enriched) if args.enriched else ENRICHED_PATH
    themes_path = Path(args.themes) if args.themes else THEMES_PATH

    if not enriched_path.exists():
        logger.error("no enriched data found at %s — run src.enrich first", enriched_path)
        return

    records = load_enriched(enriched_path)
    themes = load_themes(themes_path)
    logger.info("loaded %d evidence records, %d themes", len(records), len(themes))

    logger.info("embedding %d evidence records with %s", len(records), EMBED_MODEL_NAME)
    vectors = embed_texts([r.text for r in records])

    evidence_rows = []
    for record, vector in zip(records, vectors):
        evidence_rows.append({
            "id": record.id,
            "source": record.source,
            "url": record.url,
            "date": record.date,
            "text": record.text,
            "lang": record.lang,
            "rating": record.rating if record.rating is not None else -1,
            "categories_mentioned": json.dumps(record.categories_mentioned),
            "behaviour_signal": record.behaviour_signal,
            "barrier_type": record.barrier_type,
            "theme_id": record.theme_id,
            "family_stage": record.segment_signals.family_stage,
            "city_tier": record.segment_signals.city_tier,
            "price_sensitivity": record.segment_signals.price_sensitivity,
            "has_pet": record.segment_signals.has_pet,
            "sentiment": record.sentiment,
            "quote_worthy": record.quote_worthy,
            "vector": vector.tolist(),
        })

    theme_rows = []
    for theme in themes:
        theme_rows.append({
            "theme_id": theme["theme_id"],
            "name": theme["name"],
            "research_questions": json.dumps(theme["research_questions"]),
            "size": theme["size"],
            "prevalence": theme["prevalence"],
            "severity": theme["severity"],
            "rank_score": theme["rank_score"],
            "confidence": theme["confidence"],
            "sources": json.dumps(theme["sources"]),
            "avg_sentiment": theme["avg_sentiment"],
            "representative_quotes": json.dumps(theme["representative_quotes"]),
            "evidence_ids": json.dumps(theme["evidence_ids"]),
        })

    INDEX_DIR.parent.mkdir(parents=True, exist_ok=True)
    import lancedb

    db = lancedb.connect(str(INDEX_DIR))
    db.create_table("evidence", data=evidence_rows, mode="overwrite")
    logger.info("wrote %d rows to 'evidence' table", len(evidence_rows))

    if theme_rows:
        db.create_table("themes", data=theme_rows, mode="overwrite")
        logger.info("wrote %d rows to 'themes' table", len(theme_rows))
    else:
        logger.warning("no themes found at %s — 'themes' table not created (run src.synthesize first)", themes_path)

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "n_evidence": len(evidence_rows),
            "n_themes": len(theme_rows),
            "embed_model": EMBED_MODEL_NAME,
            "index_dir": str(INDEX_DIR),
        }, f, indent=2)

    logger.info("done: index built at %s", INDEX_DIR)


if __name__ == "__main__":
    main()
