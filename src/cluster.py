"""Phase 05 — Cluster: secondary check for a missed theme, run ONLY on the
"unclassified" subset left over after Phase 04's supervised theme_id classification.

Theming is now primarily supervised (src/enrich.py assigns each record one of the 9
fixed themes, or "unclassified", in the same LLM call as its other labels; src/synthesize
py aggregates by that label). This stage no longer drives the primary theme set — the
original all-corpus HDBSCAN run only found 3 clusters with 66% noise, too coarse to be
useful as the main mechanism. It still earns its place as a targeted second pass: run it
with --input pointed at just the unclassified records (see Usage) to check whether a
cluster emerges that's coherent and large enough to suggest the fixed taxonomy is
missing a theme. Interpret any cluster found here as a candidate to add to
src/schemas.py THEMES + prompts/enrich_batch.md, not as a theme in its own right.

Reads whatever input path is given, writes:
  - data/clustered/assignments.jsonl  (one row per record: id + cluster_id)
  - data/clustered/clusters.jsonl     (one row per cluster: name, size, representative
    quotes, dominant category/behaviour/barrier, avg sentiment)
  - data/clustered/manifest.json

Entirely local/offline (embeddings + PCA + HDBSCAN + TF-IDF), no LLM calls — this stage
does not compete with the enrich/relevance stages for the shared Gemini daily quota.

Pipeline, per docs/PhaseWiseArchitecture.md Phase 05:
  1. Embed record text with the same local model used for near-dup dedup in
     src/normalize.py (BAAI/bge-small-en-v1.5), so no new embedding model is introduced.
  2. Reduce dimensionality with PCA before clustering — high-dim cosine-normalized
     embeddings suffer distance concentration that hurts density-based clustering.
     PCA (not UMAP) is used to avoid adding a new dependency; sklearn already ships both
     PCA and HDBSCAN (added in sklearn 1.3), so no extra packages are needed.
  3. Cluster with HDBSCAN, which — unlike k-means — doesn't force every point into a
     cluster, so a genuine noise bucket surfaces rather than being hidden inside
     arbitrary clusters (see "keep the noise bucket visible" in the architecture doc).
  4. Name each cluster from its own text via TF-IDF top terms (computed against the
     rest of the corpus as background, so common words like "blinkit" don't dominate
     every cluster name) rather than an LLM call, to keep this stage quota-free.
  5. Representative quotes: the records whose embeddings are closest to the cluster's
     centroid, preferring items already flagged quote_worthy=true by Phase 04.

Usage:
    # write data/clustered/unclassified.jsonl first (filter enriched.jsonl where
    # theme_id == "unclassified"), then:
    python -m src.cluster --config config.yaml --input data/clustered/unclassified.jsonl [--min-cluster-size N]
"""
import json
from collections import Counter
from pathlib import Path
from typing import List

import numpy as np

from src.ingest.common import base_arg_parser, setup_logging
from src.schemas import EnrichedRecord

REPO_ROOT = Path(__file__).resolve().parent.parent
ENRICHED_PATH = REPO_ROOT / "data" / "enriched" / "enriched.jsonl"
DATA_CLUSTERED = REPO_ROOT / "data" / "clustered"
ASSIGNMENTS_PATH = DATA_CLUSTERED / "assignments.jsonl"
CLUSTERS_PATH = DATA_CLUSTERED / "clusters.jsonl"
MANIFEST_PATH = DATA_CLUSTERED / "manifest.json"

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"  # same model as src/normalize.py, for consistency
EMBED_BATCH_SIZE = 64
# 50 components (a common default) was grid-searched against this corpus and rejected:
# at 384-dim source embeddings, 50 PCA components still leaves enough residual
# dimensionality that HDBSCAN's density estimate suffers distance concentration (~80%
# noise). 10 components, tested across a min_cluster_size sweep, gave the best noise/
# cluster-count tradeoff (~55-67% noise, 3-4 clusters); re-tune if this corpus grows
# enough to change that balance.
PCA_COMPONENTS = 10
TOP_TERMS_PER_CLUSTER = 6
REPRESENTATIVE_QUOTES_PER_CLUSTER = 5


def load_enriched(input_path: Path, limit: int = None) -> List[EnrichedRecord]:
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(EnrichedRecord.model_validate_json(line))
            if limit is not None and len(records) >= limit:
                break
    return records


def embed_texts(texts: List[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL_NAME)
    return model.encode(
        texts, batch_size=EMBED_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=True,
    )


def reduce_dimensionality(embeddings: np.ndarray) -> np.ndarray:
    from sklearn.decomposition import PCA

    n_components = min(PCA_COMPONENTS, embeddings.shape[0] - 1, embeddings.shape[1])
    if n_components < 2:
        return embeddings
    pca = PCA(n_components=n_components, random_state=42)
    return pca.fit_transform(embeddings)


def run_hdbscan(reduced: np.ndarray, min_cluster_size: int) -> np.ndarray:
    from sklearn.cluster import HDBSCAN

    clusterer = HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
    return clusterer.fit_predict(reduced)


def top_tfidf_terms(cluster_texts: List[str], background_texts: List[str], top_n: int) -> List[str]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(
        max_df=0.9, min_df=1, stop_words="english", ngram_range=(1, 2), max_features=5000,
    )
    vectorizer.fit(background_texts)
    matrix = vectorizer.transform(cluster_texts)
    mean_scores = np.asarray(matrix.mean(axis=0)).ravel()
    top_indices = mean_scores.argsort()[::-1][:top_n]
    terms = vectorizer.get_feature_names_out()
    return [terms[i] for i in top_indices if mean_scores[i] > 0]


def representative_quotes(cluster_records: List[EnrichedRecord], cluster_embeddings: np.ndarray) -> List[dict]:
    centroid = cluster_embeddings.mean(axis=0)
    dists = np.linalg.norm(cluster_embeddings - centroid, axis=1)
    order = np.argsort(dists)
    # Prefer quote_worthy items among the closest-to-centroid, then fill with the rest.
    ranked = sorted(order, key=lambda i: (not cluster_records[i].quote_worthy, dists[i]))
    picks = ranked[:REPRESENTATIVE_QUOTES_PER_CLUSTER]
    return [
        {"id": cluster_records[i].id, "text": cluster_records[i].text, "source": cluster_records[i].source}
        for i in picks
    ]


def dominant_value(values: List[str]) -> str:
    counts = Counter(v for v in values if v and v != "none")
    if not counts:
        return "none"
    return counts.most_common(1)[0][0]


# Human-readable labels for the closed-vocabulary barrier/behaviour signals, used to
# build cluster names deterministically (no LLM call) from labels Phase 04 already
# assigned — a plain "top TF-IDF terms" name (e.g. "blinkit, product, products") reads
# as a bag of words to anyone looking at the app, not a theme.
BARRIER_LABELS = {
    "trust_quality": "Trust & Quality Concerns",
    "price_premium": "Price Premium Concerns",
    "assortment_doubt": "Assortment Doubts",
    "findability": "Findability Issues",
    "no_trigger": "No Trigger to Try",
    "returns_risk": "Returns Risk Concerns",
    "brand_absence": "Brand Absence",
    "expiry_freshness": "Expiry & Freshness Issues",
    "prefer_specialist_store": "Preference for Specialist Stores",
}
BEHAVIOUR_LABELS = {
    "habit_reorder": "Habitual Reordering",
    "discovery": "Product Discovery",
    "barrier": "General Barriers",
    "trial": "Category Trial",
    "abandonment": "Cart/Category Abandonment",
    "substitution": "Product Substitution",
    "comparison_other_platform": "Cross-Platform Comparison",
}


MIN_PREVALENCE_FOR_NAMING = 0.3  # a non-none label naming the whole cluster must actually
# describe a meaningful share of it — otherwise "most common among the few that have
# any label at all" can crown an 18-of-103 minority as the cluster's name while the
# other 80 records (barrier_type=none, mostly positive) go unrepresented.


def _prevalent_or_none(values: List[str], dominant: str) -> str:
    if dominant == "none" or not values:
        return "none"
    share = sum(1 for v in values if v == dominant) / len(values)
    return dominant if share >= MIN_PREVALENCE_FOR_NAMING else "none"


def build_cluster_name(
    dominant_category: str, dominant_behaviour: str, dominant_barrier: str, terms: List[str],
    all_behaviours: List[str] = None, all_barriers: List[str] = None,
) -> str:
    category_label = dominant_category.replace("_", " ").title() if dominant_category != "none" else None
    prevalent_barrier = _prevalent_or_none(all_barriers or [], dominant_barrier)
    prevalent_behaviour = _prevalent_or_none(all_behaviours or [], dominant_behaviour)
    label = BARRIER_LABELS.get(prevalent_barrier) or BEHAVIOUR_LABELS.get(prevalent_behaviour)
    if label and category_label:
        return f"{label} in {category_label}"
    if label:
        return label
    if terms:
        return ", ".join(terms[:3])
    return "Unnamed cluster"


def main():
    parser = base_arg_parser("Cluster enriched records into semantic themes")
    parser.add_argument("--input", default=None, help="Override input path (default: data/enriched/enriched.jsonl)")
    parser.add_argument("--min-cluster-size", type=int, default=None,
                         help="HDBSCAN min_cluster_size (default: max(5, n/100))")
    args = parser.parse_args()
    logger = setup_logging("cluster")

    input_path = Path(args.input) if args.input else ENRICHED_PATH
    if not input_path.exists():
        logger.error("no enriched data found at %s — run src.enrich first", input_path)
        return

    records = load_enriched(input_path, limit=args.limit)
    if not records:
        logger.error("no records loaded from %s", input_path)
        return

    min_cluster_size = args.min_cluster_size or max(10, len(records) // 250)
    logger.info("loaded %d enriched records; min_cluster_size=%d", len(records), min_cluster_size)

    texts = [r.text for r in records]
    logger.info("embedding %d records with %s", len(texts), EMBED_MODEL_NAME)
    embeddings = embed_texts(texts)

    logger.info("reducing dimensionality with PCA (target %d components)", PCA_COMPONENTS)
    reduced = reduce_dimensionality(embeddings)

    logger.info("clustering with HDBSCAN")
    labels = run_hdbscan(reduced, min_cluster_size)

    unique_labels = sorted(set(labels))
    n_clusters = len([l for l in unique_labels if l != -1])
    n_noise = int(np.sum(labels == -1))
    logger.info("found %d clusters, %d noise points (%.1f%%)", n_clusters, n_noise, 100 * n_noise / len(records))

    DATA_CLUSTERED.mkdir(parents=True, exist_ok=True)

    with open(ASSIGNMENTS_PATH, "w", encoding="utf-8") as f:
        for record, label in zip(records, labels):
            f.write(json.dumps({"id": record.id, "cluster_id": int(label)}) + "\n")

    all_texts = texts
    cluster_rows = []
    for label in unique_labels:
        idx = [i for i, l in enumerate(labels) if l == label]
        cluster_records = [records[i] for i in idx]
        cluster_embeddings = embeddings[idx]
        cluster_texts = [records[i].text for i in idx]

        all_categories = [c for r in cluster_records for c in r.categories_mentioned]
        behaviours = [r.behaviour_signal for r in cluster_records]
        barriers = [r.barrier_type for r in cluster_records]
        dominant_category = dominant_value(all_categories)
        dominant_behaviour = dominant_value(behaviours)
        dominant_barrier = dominant_value(barriers)

        if label == -1:
            name = "noise / unclustered"
            terms = []
        else:
            terms = top_tfidf_terms(cluster_texts, all_texts, TOP_TERMS_PER_CLUSTER)
            name = build_cluster_name(
                dominant_category, dominant_behaviour, dominant_barrier, terms,
                all_behaviours=behaviours, all_barriers=barriers,
            )

        row = {
            "cluster_id": int(label),
            "name": name,
            "top_terms": terms,
            "size": len(cluster_records),
            "dominant_category": dominant_category,
            "dominant_behaviour_signal": dominant_behaviour,
            "dominant_barrier_type": dominant_barrier,
            "avg_sentiment": round(float(np.mean([r.sentiment for r in cluster_records])), 3),
            "quote_worthy_count": sum(1 for r in cluster_records if r.quote_worthy),
            "representative_quotes": representative_quotes(cluster_records, cluster_embeddings) if label != -1 else [],
        }
        cluster_rows.append(row)

    cluster_rows.sort(key=lambda r: (r["cluster_id"] == -1, -r["size"]))
    with open(CLUSTERS_PATH, "w", encoding="utf-8") as f:
        for row in cluster_rows:
            f.write(json.dumps(row) + "\n")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total_records": len(records),
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "min_cluster_size": min_cluster_size,
            "embed_model": EMBED_MODEL_NAME,
            "pca_components": min(PCA_COMPONENTS, embeddings.shape[0] - 1, embeddings.shape[1]),
        }, f, indent=2)

    logger.info("done: wrote %d clusters + noise bucket to %s", n_clusters, CLUSTERS_PATH)


if __name__ == "__main__":
    main()
