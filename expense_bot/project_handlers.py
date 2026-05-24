from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from db import (
    create_project, set_project_budget, get_projects, get_project,
    get_project_expenses, get_project_totals, insert_project_expense,
    delete_project, get_budgets, get_period_totals_by_category
)
from parse_utils import period_label


PROJECT_HELP = """
🗂️ *Project Subcommands*

*Managing projects:*
• `/project add Malaysia Holiday --year 2027` — create a project
• `/project budget Malaysia Holiday 5000 --year 2027` — set subcategory budget
• `/project delete Malaysia Holiday --year 2027` — remove a project

*Logging expenses to a project:*
• `/add 500 project --sub Malaysia Holiday --year 2027`
• `/add 500 project --sub Malaysia Holiday` — uses current year

*Viewing:*
• `/project list` — all projects this year
• `/project list --year 2027` — all projects for a specific year
• `/project summary Malaysia Holiday` — breakdown for one project (current year)
• `/project summary Malaysia Holiday --year 2027` — specific year
• `/project summary --year 2027` — all projects for that year
"""


def _parse_year_flag(args: list[str]) -> tuple[list[str], int]:
    """Strip --year YYYY from args, return (remaining_args, year)."""
    now  = datetime.now()
    year = now.year
    out  = []
    i    = 0
    while i < len(args):
        if args[i].lower() == "--year" and i + 1 < len(args):
            try:
                year = int(args[i + 1])
                i   += 2
                continue
            except ValueError:
                pass
        out.append(args[i])
        i += 1
    return out, year


def _join_project_name(tokens: list[str]) -> str:
    return " ".join(tokens).strip()


# ── dispatcher ────────────────────────────────────────────────────────────────

async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text(PROJECT_HELP, parse_mode="Markdown")
        return

    sub = args[0].lower()
    rest = args[1:]

    if sub == "add":
        await _project_add(update, rest)
    elif sub == "budget":
        await _project_budget(update, rest)
    elif sub == "list":
        await _project_list(update, rest)
    elif sub == "summary":
        await _project_summary(update, rest)
    elif sub == "delete":
        await _project_delete(update, rest)
    elif sub == "help":
        await update.message.reply_text(PROJECT_HELP, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ Unknown subcommand `{sub}`.\n{PROJECT_HELP}",
            parse_mode="Markdown"
        )


# ── /project add ──────────────────────────────────────────────────────────────

async def _project_add(update: Update, args: list[str]):
    """
    /project add <Project Name> [--year YYYY]
    """
    remaining, year = _parse_year_flag(args)
    project_name    = _join_project_name(remaining)

    if not project_name:
        await update.message.reply_text(
            "❌ Please provide a project name.\n"
            "Example: `/project add Malaysia Holiday --year 2027`",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    create_project(user_id, project_name, year)

    await update.message.reply_text(
        f"✅ Project created!\n"
        f"🗂️ *{project_name}* — 📅 {year}\n\n"
        f"Set its budget with:\n"
        f"`/project budget {project_name} <amount> --year {year}`",
        parse_mode="Markdown"
    )


# ── /project budget ───────────────────────────────────────────────────────────

async def _project_budget(update: Update, args: list[str]):
    """
    /project budget <Project Name> <amount> [--year YYYY]
    """
    remaining, year = _parse_year_flag(args)

    # Amount is the last token that looks like a number
    if not remaining:
        await update.message.reply_text(
            "❌ Usage: `/project budget <Project Name> <amount> [--year YYYY]`",
            parse_mode="Markdown"
        )
        return

    try:
        budget = float(remaining[-1])
        project_name = _join_project_name(remaining[:-1])
    except ValueError:
        await update.message.reply_text(
            "❌ Amount must be a number and placed last.\n"
            "Example: `/project budget Malaysia Holiday 5000 --year 2027`",
            parse_mode="Markdown"
        )
        return

    if not project_name:
        await update.message.reply_text(
            "❌ Please provide a project name before the amount.",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    set_project_budget(user_id, project_name, year, budget)

    # Check against parent project envelope
    parent_budgets = get_budgets(user_id, "annual", None, year)
    parent_info    = parent_budgets.get("project")
    warning        = ""
    if parent_info:
        projects      = get_projects(user_id, year)
        total_sub_budget = sum(
            p["budget"] for p in projects if p["budget"] is not None
        )
        if total_sub_budget > parent_info["limit"]:
            warning = (
                f"\n\n⚠️ Note: total subcategory budgets (`${total_sub_budget:.2f}`) "
                f"now exceed the overall project envelope (`${parent_info['limit']:.2f}`)."
            )

    await update.message.reply_text(
        f"✅ Budget set!\n"
        f"🗂️ *{project_name}* → `${budget:.2f}` for 📅 {year}{warning}",
        parse_mode="Markdown"
    )


# ── /project list ─────────────────────────────────────────────────────────────

async def _project_list(update: Update, args: list[str]):
    """
    /project list [--year YYYY]
    """
    _, year     = _parse_year_flag(args)
    user_id     = update.effective_user.id
    projects    = get_projects(user_id, year)
    totals      = get_project_totals(user_id, year)

    # Parent envelope
    parent_budgets = get_budgets(user_id, "annual", None, year)
    parent_info    = parent_budgets.get("project")
    parent_spent   = get_period_totals_by_category(user_id, "annual", None, year).get("project", 0)

    if not projects:
        await update.message.reply_text(
            f"No projects found for 📅 {year}.\n"
            f"Create one with `/project add <name> --year {year}`",
            parse_mode="Markdown"
        )
        return

    lines = [f"🗂️ *Projects — 📅 {year}*\n"]

    if parent_info:
        pct    = (parent_spent / parent_info["limit"]) * 100
        status = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
        lines.append(
            f"{status} *Overall Project Envelope*\n"
            f"   `${parent_spent:.2f}` / `${parent_info['limit']:.2f}` ({pct:.0f}%)\n"
        )

    lines.append("*Subcategories:*")
    total_sub_budget = 0
    for p in projects:
        spent  = totals.get(p["name"], 0)
        budget = p["budget"]
        if budget:
            total_sub_budget += budget
            pct    = (spent / budget) * 100
            bar    = _progress_bar(pct)
            status = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
            lines.append(
                f"\n{status} 📁 *{p['name']}*\n"
                f"   `${spent:.2f}` / `${budget:.2f}` ({pct:.0f}%)\n"
                f"   {bar}"
            )
        else:
            lines.append(
                f"\n📁 *{p['name']}*\n"
                f"   `${spent:.2f}` spent _(no budget set)_"
            )

    if parent_info and total_sub_budget > 0:
        remaining = parent_info["limit"] - total_sub_budget
        lines.append(
            f"\n💼 Sub-budgets total: `${total_sub_budget:.2f}` / `${parent_info['limit']:.2f}` envelope"
            + (f"\n   ⚠️ `${abs(remaining):.2f}` over envelope!" if remaining < 0
               else f"\n   `${remaining:.2f}` unallocated in envelope")
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /project summary ──────────────────────────────────────────────────────────

async def _project_summary(update: Update, args: list[str]):
    """
    /project summary [Project Name] [--year YYYY]
    All projects if no name given.
    """
    remaining, year = _parse_year_flag(args)
    project_name    = _join_project_name(remaining)
    user_id         = update.effective_user.id

    if project_name:
        # Single project summary
        project = get_project(user_id, project_name, year)
        if not project:
            await update.message.reply_text(
                f"❌ Project *{project_name}* not found for 📅 {year}.\n"
                f"Use `/project list --year {year}` to see all projects.",
                parse_mode="Markdown"
            )
            return

        expenses = get_project_expenses(user_id, project_name, year)
        total    = sum(e["amount"] for e in expenses)
        budget   = project["budget"]

        lines = [f"📁 *{project_name}* — 📅 {year}\n"]

        if budget:
            pct    = (total / budget) * 100
            bar    = _progress_bar(pct)
            status = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
            lines.append(f"{status} `${total:.2f}` / `${budget:.2f}` ({pct:.0f}%)")
            lines.append(bar)
        else:
            lines.append(f"💰 Total spent: `${total:.2f}` _(no budget set)_")

        if expenses:
            lines.append("\n*Expenses:*")
            for e in expenses:
                lines.append(f"  • `${e['amount']:.2f}` — {e['note'] or '—'} _{e['date']}_")
        else:
            lines.append("\n_No expenses logged yet._")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    else:
        # All projects summary for the year
        await _project_list(update, [f"--year", str(year)])


# ── /project delete ───────────────────────────────────────────────────────────

async def _project_delete(update: Update, args: list[str]):
    """
    /project delete <Project Name> [--year YYYY]
    """
    remaining, year = _parse_year_flag(args)
    project_name    = _join_project_name(remaining)

    if not project_name:
        await update.message.reply_text(
            "❌ Please provide a project name to delete.\n"
            "Example: `/project delete Malaysia Holiday --year 2027`",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    project = get_project(user_id, project_name, year)

    if not project:
        await update.message.reply_text(
            f"❌ Project *{project_name}* not found for 📅 {year}.",
            parse_mode="Markdown"
        )
        return

    delete_project(user_id, project_name, year)
    await update.message.reply_text(
        f"🗑️ Project *{project_name}* (📅 {year}) has been deleted.",
        parse_mode="Markdown"
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _progress_bar(pct: float, length: int = 10) -> str:
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)
