# ─────────────────────────────────────────────
#  Category definitions
#  Edit this file to add / remove / rename categories
# ─────────────────────────────────────────────

MONTHLY_CATEGORIES = {
    "Short-term":           "🛍️",
    "monthly subscription": "📦",
    "tax":                  "🧾",
    "stipend":              "💸",
}

ANNUAL_CATEGORIES = {
    "insurance":        "🛡️",
    "investment":       "📈",
    "annual membership":"🪪",
    "project":          "🗂️",
}

# Merged lookup (used for emoji resolution)
ALL_CATEGORIES = {**MONTHLY_CATEGORIES, **ANNUAL_CATEGORIES}

MONTHLY_KEYS = list(MONTHLY_CATEGORIES.keys())
ANNUAL_KEYS  = list(ANNUAL_CATEGORIES.keys())
ALL_KEYS     = MONTHLY_KEYS + ANNUAL_KEYS

DEFAULT_EMOJI = "💰"


def emoji_for(category: str) -> str:
    return ALL_CATEGORIES.get(category.lower(), DEFAULT_EMOJI)


def is_valid_category(category: str) -> bool:
    return category.lower() in ALL_CATEGORIES


def is_monthly(category: str) -> bool:
    return category.lower() in MONTHLY_CATEGORIES


def is_annual(category: str) -> bool:
    return category.lower() in ANNUAL_CATEGORIES


def category_type_label(category: str) -> str:
    if is_monthly(category):
        return "monthly"
    if is_annual(category):
        return "annual"
    return "unknown"
