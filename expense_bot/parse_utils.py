from datetime import datetime

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

MONTH_LABELS = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def parse_flags(args: list[str], category_type: str):
    """
    Strips --month / --year flags from an arg list.

    Returns:
        note (str), period_month (int|None), period_year (int|None), error (str|None)

    Supported flag formats:
        --month June 2026   → month=6, year=2026
        --month June        → month=6, year=current
        --year 2027         → year=2027 (annual only)
    """
    now = datetime.now()
    period_month = None
    period_year  = None
    note_parts   = []
    error        = None

    i = 0
    while i < len(args):
        token = args[i].lower()

        if token == "--month":
            if category_type == "annual":
                error = "Annual expenses use `--year`, not `--month`."
                return "", None, None, error
            # expect: MonthName [Year]
            if i + 1 >= len(args):
                error = "Please provide a month after `--month`. E.g. `--month June 2026`"
                return "", None, None, error
            month_str = args[i + 1].lower()
            if month_str not in MONTH_NAMES:
                error = f"Unrecognised month `{args[i+1]}`. Use full name e.g. `June`."
                return "", None, None, error
            period_month = MONTH_NAMES[month_str]
            i += 2
            # optional year right after
            if i < len(args):
                try:
                    y = int(args[i])
                    if 2000 <= y <= 2100:
                        period_year = y
                        i += 1
                except ValueError:
                    pass

        elif token == "--year":
            if i + 1 >= len(args):
                error = "Please provide a year after `--year`. E.g. `--year 2027`"
                return "", None, None, error
            try:
                y = int(args[i + 1])
                if 2000 <= y <= 2100:
                    period_year = y
                    i += 2
                else:
                    error = "Year must be between 2000 and 2100."
                    return "", None, None, error
            except ValueError:
                error = f"Invalid year `{args[i+1]}`."
                return "", None, None, error

        elif token == "--recurring":
            # leave for caller to handle
            note_parts.append(args[i])
            i += 1

        else:
            note_parts.append(args[i])
            i += 1

    # Defaults
    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    note = " ".join(note_parts)
    return note, period_month, period_year, None


def parse_period_args(args: list[str], category_type: str):
    """
    Parse period from command args like:
      []                   → current month/year
      ["June", "2026"]     → month=6, year=2026
      ["2027"]             → year=2027 (annual)
      ["annual"]           → annual, current year
      ["annual", "2027"]   → annual, year=2027

    Returns: category_type, period_month, period_year
    """
    now = datetime.now()
    period_month = None
    period_year  = None

    tokens = [a.lower() for a in args]

    # strip "annual" / "monthly" tokens
    if "annual" in tokens:
        category_type = "annual"
        tokens = [t for t in tokens if t != "annual"]
    elif "monthly" in tokens:
        category_type = "monthly"
        tokens = [t for t in tokens if t != "monthly"]

    for token in tokens:
        if token in MONTH_NAMES:
            period_month = MONTH_NAMES[token]
        else:
            try:
                y = int(token)
                if 2000 <= y <= 2100:
                    period_year = y
            except ValueError:
                pass

    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    return category_type, period_month, period_year


def period_label(category_type: str, period_month: int, period_year: int) -> str:
    """Human-readable period label. E.g. 'May 2026' or '2027'."""
    if category_type == "annual":
        return str(period_year)
    return f"{MONTH_LABELS.get(period_month, '?')} {period_year}"
