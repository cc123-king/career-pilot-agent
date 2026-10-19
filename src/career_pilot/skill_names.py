"""Explicit skill aliases shared by matching, coaching and interview evidence."""

import unicodedata

from career_pilot.text_utils import normalize_text

# Only equivalent names are mapped. Related technologies remain distinct.
SKILL_ALIASES = {
    "fast api": "fastapi",
    "fast-api": "fastapi",
    "postgre sql": "postgresql",
    "postgres": "postgresql",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "py torch": "pytorch",
}
SKILL_NORMALIZATION_VERSION = "explicit-aliases-v1"


def canonical_skill_key(skill: str) -> str:
    key = normalize_text(unicodedata.normalize("NFKC", skill)).casefold()
    return SKILL_ALIASES.get(key, key)
