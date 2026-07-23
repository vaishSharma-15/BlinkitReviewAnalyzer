import re

DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
ALPHA_RE = re.compile(r"[A-Za-zऀ-ॿ]")
WORD_RE = re.compile(r"[A-Za-z']+")

# Common romanized Hindi/Hinglish tokens. A heuristic lexicon rather than a trained
# model, kept deterministic and auditable per the project's enrichment principles.
HINGLISH_TOKENS = {
    "hai", "hain", "nahi", "nahin", "kya", "kyu", "kyun", "acha", "accha", "bhai",
    "yaar", "bahut", "bohot", "matlab", "karo", "kar", "raha", "rha", "rahi", "mujhe",
    "tumhe", "aap", "apna", "wala", "wale", "hoga", "hogi", "thoda", "bilkul", "sahi",
    "galat", "paisa", "paise", "chahiye", "milta", "milti", "mila", "mili", "dikkat",
    "pareshani", "bekar", "badiya", "theek", "thik", "abhi", "kabhi", "kuch", "sab",
    "iska", "uska", "isse", "usse", "krna", "krte", "krke", "plzz", "plz",
}


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "other"

    devanagari_chars = len(DEVANAGARI_RE.findall(text))
    alpha_chars = len(ALPHA_RE.findall(text))
    if alpha_chars == 0:
        return "other"

    if devanagari_chars / alpha_chars > 0.3:
        return "hi"

    words = [w.lower() for w in WORD_RE.findall(text)]
    if not words:
        return "other"

    hinglish_hits = sum(1 for w in words if w in HINGLISH_TOKENS)
    if hinglish_hits >= 2 or (len(words) <= 6 and hinglish_hits >= 1):
        return "hinglish"

    return "en"
