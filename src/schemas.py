from typing import Any, Dict, List, Optional

from pydantic import BaseModel

CATEGORIES = [
    "grocery_staples", "fruits_vegetables", "dairy_bakery", "snacks_beverages",
    "household_essentials", "personal_care_beauty", "baby_care", "pet_supplies",
    "electronics_accessories", "home_kitchen", "toys_stationery", "gifting_festival",
    "pharmacy_wellness", "other",
]

BEHAVIOUR_SIGNAL = [
    "habit_reorder", "discovery", "barrier", "trial", "abandonment",
    "substitution", "comparison_other_platform", "none",
]

BARRIER_TYPE = [
    "trust_quality", "price_premium", "assortment_doubt", "findability",
    "no_trigger", "returns_risk", "brand_absence", "expiry_freshness",
    "prefer_specialist_store", "none",
]

# Fixed 9-theme taxonomy (replaces unsupervised HDBSCAN clustering as the primary
# theming mechanism — see src/enrich.py and src/synthesize.py). "unclassified" is the
# closed-vocabulary escape hatch for items that speak to shopping behaviour (they passed
# the Phase 03 relevance gate) but don't fit any of the 9 themes; those get a second,
# offline pass through src/cluster.py as a check for a missed theme, not a silent drop.
THEMES = [
    "platform_mental_model", "category_specific_distrust", "first_trial_story",
    "habit_and_reorder", "discovery_mechanics", "assortment_gaps", "price_and_value",
    "life_event_trigger", "cross_platform_comparison", "unclassified",
]

SOURCES = ["play", "appstore", "reddit", "youtube", "forum", "product_review", "qcomm_comparison"]

LANGUAGES = ["en", "hi", "hinglish", "other"]

FAMILY_STAGE = ["parent_young_child", "single", "couple", "unknown"]
CITY_TIER = ["metro", "tier2", "unknown"]
PRICE_SENSITIVITY = ["high", "low", "unknown"]
HAS_PET = ["yes", "no", "unknown"]

# The eight required output slots, per docs/ProblemStatement.md §4. Every one must be
# answered by at least one theme with cited evidence, or explicitly marked unanswerable
# by src/synthesize.py — never silently skipped.
RESEARCH_QUESTIONS = {
    "Q1": "Why do users repeatedly buy from the same categories?",
    "Q2": "What prevents users from exploring new categories?",
    "Q3": "How do users discover products on the platform today?",
    "Q4": "What role do habits/routines/reorder behaviour play?",
    "Q5": "What information does a user need before trying a new category for the first time?",
    "Q6": "What frustrations emerge repeatedly?",
    "Q7": "Which user segments are more likely to experiment?",
    "Q8": "What unmet needs emerge consistently across independent sources?",
}


class RawRecord(BaseModel):
    id: str
    source: str
    url: str
    date: str
    text: str
    rating: Optional[int] = None
    meta: Dict[str, Any] = {}


class NormalizedRecord(BaseModel):
    id: str
    source: str
    url: str
    date: str
    text: str
    rating: Optional[int] = None
    lang: str
    meta: Dict[str, Any] = {}


class SegmentSignals(BaseModel):
    family_stage: str = "unknown"
    city_tier: str = "unknown"
    price_sensitivity: str = "unknown"
    has_pet: str = "unknown"


class EnrichedRecord(BaseModel):
    id: str
    source: str
    url: str
    date: str
    text: str
    lang: str
    rating: Optional[int] = None
    relevant: bool = True
    relevance_reason: str = ""
    categories_mentioned: List[str] = []
    behaviour_signal: str
    barrier_type: str
    theme_id: str = "unclassified"
    segment_signals: SegmentSignals
    sentiment: float
    quote_worthy: bool
    prompt_version: str
    meta: Dict[str, Any] = {}
