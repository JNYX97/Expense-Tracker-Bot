from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from categories import (
    emoji_for, is_valid_category, category_type_label,
    MONTHLY_CATEGORIES, ANNUAL_CATEGORIES, MONTHLY_KEYS, ANNUAL_KEYS
)
from db import (
    insert_expense, get_expenses_by_period, get_recurring_expenses,
    get_period_totals_by_category, set_budget_db, get_budgets,
    insert_project_expense, get_project, get_project_totals, get_projects
)
from parse_utils import parse_flags, parse_period_args, period_label, MONTH_NAMES
from charts import generate_alerts_chart


# ── /start & /help ────────────────────────────────────────────────────────────

HELP_TEXT = """
💸 *Personal Expense Tracker*
Tracks spendature against short term goals (across the month) and mid term goals (across the year)

*Monthly categories:* short term, monthly subscription, tax, stipend
*Annual categories:* insurance, investment, annual membership, project

*Logging expenses:*
• `/add 12.50 short term Chicken rice --recurring 30` — logs to current month (May 2026)
• `/add 500 short term shopping Clothes --month June 2026` — logs to June 2026
• `/add 2000 project Malaysia Trip --year 2027` — logs to annual 2027
• `/add 800 project --sub Malaysia Holiday --year 2027` — logs to sub-project, annual 2027
• `/project add Malaysia Holiday --year 2027` — creates new sub-project, annual 2027


*Budgets:*
• `/budget food 400` — set budget for current month
• `/budget food 400 --month June 2026` — set budget for specific month
• `/budget insurance 1200 --year 2027` — set annual budget for 2027
• `/project budget Malaysia Holiday 5000 --year 2027` — set sub-project budget for 2027

*Viewing:*
• `/list` — expenses this month
• `/list June 2026` — expenses for a specific month
• `/list annual` — mid-term expenses this year
• `/list annual 2027` — expenses for a specific year
• `/summary` — spending vs budget this month
• `/summary June 2026` — specific month summary
• `/summary annual` — this year's annual summary
• `/summary annual 2027` — specific year summary
• `/project list --year 2027` — project list for specific year
• `/project summary Malaysia Holiday --year 2027`  — specific year summary
• `/projection 30` — project next 30 days
• `/alerts` — budgets nearing their limit
• `/categories` — show all valid categories
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 *Welcome to your Personal Expense Tracker!*\n{HELP_TEXT}",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


# ── /categories ───────────────────────────────────────────────────────────────

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monthly_lines = "\n".join(f"  {emoji} `{cat}`" for cat, emoji in MONTHLY_CATEGORIES.items())
    annual_lines  = "\n".join(f"  {emoji} `{cat}`" for cat, emoji in ANNUAL_CATEGORIES.items())
    await update.message.reply_text(
        f"📋 *Available Categories*\n\n"
        f"🗓 *Monthly*\n{monthly_lines}\n\n"
        f"📅 *Annual*\n{annual_lines}",
        parse_mode="Markdown"
    )


# ── /add ──────────────────────────────────────────────────────────────────────

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /add <amount> <category> [note] [--month Month [Year]] [--year Year]
                             [--sub Project Name] [--recurring [days]]

    Examples:
      /add 12.50 food Chicken rice
      /add 500 shopping Clothes --month June 2026
      /add 2000 project --sub Malaysia Holiday --year 2027
      /add 50 monthly subscription Netflix --recurring 30
    """
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: `/add <amount> <category> [note] [--month Month Year] [--year Year] [--sub Project Name]`\n"
            "Use `/categories` to see valid categories.",
            parse_mode="Markdown"
        )
        return

    # Parse amount
    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number. E.g. `/add 12.50 food`", parse_mode="Markdown")
        return

    # Detect category (support 2-word categories)
    category = None
    rest_start = 2
    if len(args) >= 3:
        two_word = f"{args[1]} {args[2]}".lower()
        if is_valid_category(two_word):
            category = two_word
            rest_start = 3

    if category is None:
        one_word = args[1].lower()
        if is_valid_category(one_word):
            category = one_word
            rest_start = 2

    if category is None:
        monthly_list = ", ".join(f"`{c}`" for c in MONTHLY_KEYS)
        annual_list  = ", ".join(f"`{c}`" for c in ANNUAL_KEYS)
        await update.message.reply_text(
            f"❌ Unknown category: `{args[1]}`\n\n"
            f"🗓 Monthly: {monthly_list}\n"
            f"📅 Annual: {annual_list}",
            parse_mode="Markdown"
        )
        return

    cat_type = category_type_label(category)

    # Parse flags + note from remaining args
    remaining = args[rest_start:]

    # Extract --sub, --recurring before passing to parse_flags
    is_recurring    = False
    recurrence_days = 365 if cat_type == "annual" else 30
    sub_project     = None
    clean_remaining = []
    i = 0
    while i < len(remaining):
        tok = remaining[i].lower()
        if tok == "--recurring":
            is_recurring = True
            if i + 1 < len(remaining):
                try:
                    recurrence_days = int(remaining[i + 1])
                    i += 2
                    continue
                except ValueError:
                    pass
            i += 1
        elif tok == "--sub":
            # Collect all tokens until the next -- flag as the project name
            i += 1
            sub_parts = []
            while i < len(remaining) and not remaining[i].startswith("--"):
                sub_parts.append(remaining[i])
                i += 1
            sub_project = " ".join(sub_parts).strip()
        else:
            clean_remaining.append(remaining[i])
            i += 1

    note, period_month, period_year, error = parse_flags(clean_remaining, cat_type)
    if error:
        await update.message.reply_text(f"❌ {error}", parse_mode="Markdown")
        return

    user_id = update.effective_user.id

    # ── Project subcategory path ───────────────────────────────────────────────
    if sub_project and category == "project":
        project = get_project(user_id, sub_project, period_year)
        if not project:
            await update.message.reply_text(
                f"❌ Project *{sub_project}* not found for 📅 {period_year}.\n"
                f"Create it first with `/project add {sub_project} --year {period_year}`",
                parse_mode="Markdown"
            )
            return

        insert_project_expense(user_id, sub_project, period_year, amount, note)

        budget  = project["budget"]
        totals  = get_project_totals(user_id, period_year)
        spent   = totals.get(sub_project, 0) + amount
        warning = ""
        if budget and spent > budget:
            warning = f"\n\n⚠️ This project is now over its budget of `${budget:.2f}`!"

        await update.message.reply_text(
            f"🗂️ *Project expense logged!*\n"
            f"Amount:  `${amount:.2f}`\n"
            f"Project: *{sub_project}*\n"
            f"Period:  📅 `{period_year}`\n"
            f"Note:    {note or '—'}{warning}",
            parse_mode="Markdown"
        )
        return

    # ── Standard expense path ─────────────────────────────────────────────────
    insert_expense(
        user_id, amount, category, cat_type, note,
        period_month, period_year, is_recurring, recurrence_days
    )

    plabel     = period_label(cat_type, period_month, period_year)
    period_icon = "📅" if cat_type == "annual" else "🗓"
    rec_label   = f"🔁 recurring every {recurrence_days} days" if is_recurring else "one-time"

    await update.message.reply_text(
        f"{emoji_for(category)} *Expense logged!*\n"
        f"Amount:   `${amount:.2f}`\n"
        f"Category: `{category}`\n"
        f"Period:   {period_icon} `{plabel}`\n"
        f"Note:     {note or '—'}\n"
        f"Type:     {rec_label}",
        parse_mode="Markdown"
    )


# ── /list ─────────────────────────────────────────────────────────────────────

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /list                  — this month
    /list June 2026        — specific month
    /list annual           — this year
    /list annual 2027      — specific year
    """
    user_id = update.effective_user.id
    args    = context.args or []

    cat_type, period_month, period_year = parse_period_args(args, "monthly")
    expenses = get_expenses_by_period(user_id, cat_type, period_month, period_year)

    plabel = period_label(cat_type, period_month, period_year)
    period_icon = "📅" if cat_type == "annual" else "🗓"

    if not expenses:
        await update.message.reply_text(
            f"No {cat_type} expenses found for {period_icon} *{plabel}*.",
            parse_mode="Markdown"
        )
        return

    lines = [f"📋 *{period_icon} Expenses — {plabel}*\n"]
    total = 0
    for amount, category, c_type, note, date, is_recurring, p_month, p_year in expenses:
        rec = " 🔁" if is_recurring else ""
        lines.append(
            f"{emoji_for(category)} `${amount:.2f}` — {category} | {note or '—'}{rec}"
        )
        total += amount

    lines.append(f"\n💰 *Total: ${total:.2f}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /budget ───────────────────────────────────────────────────────────────────

async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /budget food 400                      — current month
    /budget food 400 --month June 2026    — specific month
    /budget insurance 1200 --year 2027    — specific year (annual)
    /budget annual membership 500 --year 2026  — 2-word category
    """
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: `/budget <category> <amount> [--month Month Year] [--year Year]`",
            parse_mode="Markdown"
        )
        return

    # Detect category (1 or 2 word)
    category  = None
    amount_idx = 1
    if len(args) >= 3:
        two_word = f"{args[0]} {args[1]}".lower()
        if is_valid_category(two_word):
            category   = two_word
            amount_idx = 2

    if category is None:
        one_word = args[0].lower()
        if is_valid_category(one_word):
            category   = one_word
            amount_idx = 1

    if category is None:
        await update.message.reply_text(
            f"❌ Unknown category: `{args[0]}`\nUse `/categories` to see valid options.",
            parse_mode="Markdown"
        )
        return

    try:
        limit = float(args[amount_idx])
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Limit must be a number.", parse_mode="Markdown")
        return

    cat_type   = category_type_label(category)
    flag_args  = args[amount_idx + 1:]
    _, period_month, period_year, error = parse_flags(flag_args, cat_type)
    if error:
        await update.message.reply_text(f"❌ {error}", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    set_budget_db(user_id, category, cat_type, limit, period_month, period_year)

    plabel      = period_label(cat_type, period_month, period_year)
    period_icon = "📅" if cat_type == "annual" else "🗓"

    await update.message.reply_text(
        f"✅ Budget set!\n"
        f"{emoji_for(category)} `{category}` → `${limit:.2f}` for {period_icon} *{plabel}*",
        parse_mode="Markdown"
    )


# ── /summary ──────────────────────────────────────────────────────────────────

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /summary               — this month
    /summary June 2026     — specific month
    /summary annual        — this year
    /summary annual 2027   — specific year
    """
    user_id = update.effective_user.id
    args    = context.args or []

    cat_type, period_month, period_year = parse_period_args(args, "monthly")
    totals  = get_period_totals_by_category(user_id, cat_type, period_month, period_year)
    budgets = get_budgets(user_id, cat_type, period_month, period_year)

    plabel      = period_label(cat_type, period_month, period_year)
    period_icon = "📅" if cat_type == "annual" else "🗓"

    if not totals and not budgets:
        await update.message.reply_text(
            f"No data found for {period_icon} *{plabel}*.",
            parse_mode="Markdown"
        )
        return

    lines       = [f"📊 *{period_icon} Summary — {plabel}*\n"]
    grand_total = 0

    all_cats = set(totals.keys()) | set(budgets.keys())
    for cat in sorted(all_cats):
        spent       = totals.get(cat, 0)
        budget_info = budgets.get(cat)
        grand_total += spent

        if budget_info:
            limit  = budget_info["limit"]
            pct    = (spent / limit) * 100
            bar    = _progress_bar(pct)
            status = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
            lines.append(
                f"{status} {emoji_for(cat)} *{cat}*\n"
                f"   `${spent:.2f}` / `${limit:.2f}` ({pct:.0f}%)\n"
                f"   {bar}"
            )
        else:
            lines.append(f"{emoji_for(cat)} *{cat}*: `${spent:.2f}` _(no budget set)_")

    lines.append(f"\n💰 *Total: ${grand_total:.2f}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /projection ───────────────────────────────────────────────────────────────

async def show_projection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /projection 30    — monthly projection for next 30 days
    /projection 365   — annual projection for next 365 days
    """
    user_id = update.effective_user.id
    days    = 30
    if context.args:
        try:
            days = int(context.args[0])
        except ValueError:
            pass

    cat_type = "annual" if days >= 180 else "monthly"
    now      = datetime.now()

    recurring     = get_recurring_expenses(user_id, cat_type)
    recurring_proj: dict[str, float] = {}
    for amount, category, c_type, note, recurrence_days in recurring:
        occurrences = days / recurrence_days
        recurring_proj[category] = recurring_proj.get(category, 0) + amount * occurrences

    lookback = 365 if cat_type == "annual" else 30
    past     = get_expenses_by_period(
        user_id, cat_type,
        period_month = now.month if cat_type == "monthly" else None,
        period_year  = now.year
    )
    daily_avg: dict[str, float] = {}
    for amount, category, c_type, note, date, is_recurring, p_month, p_year in past:
        if not is_recurring:
            daily_avg[category] = daily_avg.get(category, 0) + amount / lookback

    scaled   = {cat: avg * days for cat, avg in daily_avg.items()}
    all_cats = set(recurring_proj.keys()) | set(scaled.keys())

    if not all_cats:
        await update.message.reply_text(
            "No data to project from yet. Start adding expenses with `/add`!",
            parse_mode="Markdown"
        )
        return

    budgets     = get_budgets(user_id, cat_type)
    period_icon = "📅" if cat_type == "annual" else "🗓"
    lines       = [f"🔮 *{period_icon} Projection — next {days} days*\n"]
    grand_total = 0

    for cat in sorted(all_cats):
        proj        = recurring_proj.get(cat, 0) + scaled.get(cat, 0)
        grand_total += proj
        budget_info = budgets.get(cat)

        if budget_info:
            limit = budget_info["limit"]
            pct   = (proj / limit) * 100
            flag  = " ⚠️" if pct > 90 else ""
            lines.append(f"{emoji_for(cat)} *{cat}*: `${proj:.2f}` / `${limit:.2f}` ({pct:.0f}%){flag}")
        else:
            lines.append(f"{emoji_for(cat)} *{cat}*: `${proj:.2f}`")

    lines.append(f"\n💸 *Total projected: ${grand_total:.2f}*")
    lines.append("_(Based on recurring expenses + recent spending average)_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /alerts ───────────────────────────────────────────────────────────────────

async def check_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now     = datetime.now()

    monthly_budgets = get_budgets(user_id, "monthly", now.month, now.year)
    annual_budgets  = get_budgets(user_id, "annual",  None,      now.year)
    all_budgets     = {**monthly_budgets, **annual_budgets}

    if not all_budgets:
        await update.message.reply_text(
            "You haven't set any budgets yet. Use `/budget <category> <amount>`.",
            parse_mode="Markdown"
        )
        return

    monthly_totals = get_period_totals_by_category(user_id, "monthly", now.month, now.year)
    annual_totals  = get_period_totals_by_category(user_id, "annual",  None,      now.year)

    alerts      = []
    safe        = []
    budget_data = []   # collected for pie chart

    for cat, info in all_budgets.items():
        limit    = info["limit"]
        cat_type = info["type"]
        totals   = annual_totals if cat_type == "annual" else monthly_totals
        spent    = totals.get(cat, 0)
        pct      = (spent / limit) * 100
        period   = "📅" if cat_type == "annual" else "🗓"

        budget_data.append({
            "category": cat,
            "spent":    spent,
            "limit":    limit,
            "cat_type": cat_type,
        })

        if pct >= 100:
            alerts.append(f"🔴 {period} *{cat}*: OVER BUDGET! `${spent:.2f}` / `${limit:.2f}` ({pct:.0f}%)")
        elif pct >= 80:
            alerts.append(f"🟡 {period} *{cat}*: nearing limit — `${spent:.2f}` / `${limit:.2f}` ({pct:.0f}%)")
        else:
            safe.append(f"🟢 {period} *{cat}*: `${spent:.2f}` / `${limit:.2f}` ({pct:.0f}%)")

    # ── 1. Text summary ────────────────────────────────────────────────────────
    lines = ["🚨 *Budget Alerts — Current Period*\n"]
    lines += alerts if alerts else ["No alerts — you're within all budgets! 🎉"]
    if safe:
        lines.append("\n✅ *On track:*")
        lines += safe

    # ── Project subcategory alerts ────────────────────────────────────────────
    projects       = get_projects(user_id, now.year)
    project_totals = get_project_totals(user_id, now.year)
    proj_alerts    = []
    proj_safe      = []

    for p in projects:
        budget = p["budget"]
        if budget is None:
            continue
        spent = project_totals.get(p["name"], 0)
        pct   = (spent / budget) * 100
        if pct >= 100:
            proj_alerts.append(f"🔴 🗂️ *{p['name']}*: OVER! `${spent:.2f}` / `${budget:.2f}` ({pct:.0f}%)")
            budget_data.append({"category": p["name"], "spent": spent, "limit": budget, "cat_type": "annual"})
        elif pct >= 80:
            proj_alerts.append(f"🟡 🗂️ *{p['name']}*: nearing — `${spent:.2f}` / `${budget:.2f}` ({pct:.0f}%)")
            budget_data.append({"category": p["name"], "spent": spent, "limit": budget, "cat_type": "annual"})
        else:
            proj_safe.append(f"🟢 🗂️ *{p['name']}*: `${spent:.2f}` / `${budget:.2f}` ({pct:.0f}%)")

    if proj_alerts or proj_safe:
        lines.append("\n📁 *Project Subcategories:*")
        lines += proj_alerts if proj_alerts else []
        if proj_safe:
            lines += proj_safe

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── 2. Pie chart ───────────────────────────────────────────────────────────
    try:
        chart_buf = generate_alerts_chart(budget_data)
        await update.message.reply_photo(
            photo=chart_buf,
            caption="📊 Spending vs Budget — current period"
        )
    except Exception as e:
        await update.message.reply_text(f"_(Chart unavailable: {e})_", parse_mode="Markdown")


# ── cancel ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")


# ── helpers ───────────────────────────────────────────────────────────────────

def _progress_bar(pct: float, length: int = 10) -> str:
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)

# ── /remove ───────────────────────────────────────────────────────────────────
# Uses a simple conversation state stored in context.user_data

REMOVE_AWAITING = "remove_awaiting_selection"


async def remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /remove — shows last 10 entries and asks user to pick one to delete.
    """
    user_id = update.effective_user.id
    entries = get_recent_entries(user_id, limit=10)

    if not entries:
        await update.message.reply_text("No expenses found to remove.")
        return

    lines = ["🗑️ *Recent entries — reply with the number to remove:*\n"]
    for i, row in enumerate(entries, start=1):
        source, entry_id, amount, category, note, date, p_month, p_year = row
        if source == "project":
            label = f"📁 `${amount:.2f}` — project [{category}] | {note or '—'} | 📅 {p_year}"
        else:
            period = f"📅 {p_year}" if p_month is None else f"🗓 {p_year}-{p_month:02d}"
            label  = f"{emoji_for(category)} `${amount:.2f}` — {category} | {note or '—'} | {period}"
        lines.append(f"{i}. {label}")

    lines.append("\n_Reply with a number to delete, or /cancel to abort._")

    # Store entries in user_data for the next message
    context.user_data[REMOVE_AWAITING] = entries
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the user's numeric reply after /remove.
    """
    entries = context.user_data.get(REMOVE_AWAITING)
    if not entries:
        return  # not in a remove flow, ignore

    text    = update.message.text.strip()
    user_id = update.effective_user.id

    # Allow /cancel mid-flow
    if text.lower() in ("/cancel", "cancel"):
        context.user_data.pop(REMOVE_AWAITING, None)
        await update.message.reply_text("❌ Removal cancelled.")
        return

    try:
        choice = int(text)
    except ValueError:
        await update.message.reply_text(
            "Please reply with a *number* from the list, or /cancel to abort.",
            parse_mode="Markdown"
        )
        return

    if choice < 1 or choice > len(entries):
        await update.message.reply_text(
            f"Please enter a number between 1 and {len(entries)}, or /cancel to abort.",
            parse_mode="Markdown"
        )
        return

    row = entries[choice - 1]
    source, entry_id, amount, category, note, date, p_month, p_year = row

    if source == "project":
        delete_project_expense(user_id, entry_id)
        desc = f"📁 project [{category}] — `${amount:.2f}` | {note or '—'} | 📅 {p_year}"
    else:
        delete_expense(user_id, entry_id)
        period = f"📅 {p_year}" if p_month is None else f"🗓 {p_year}-{p_month:02d}"
        desc   = f"{emoji_for(category)} {category} — `${amount:.2f}` | {note or '—'} | {period}"

    context.user_data.pop(REMOVE_AWAITING, None)
    await update.message.reply_text(
        f"✅ *Entry removed:*\n{desc}",
        parse_mode="Markdown"
    )
