import os
import logging
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv
from db import init_db
from handlers import (
    start, help_command, add_expense, list_expenses,
    set_budget, show_summary, show_projection,
    check_alerts, show_categories, cancel
)
from project_handlers import project_command

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def main():
    init_db()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("help",       help_command))
    app.add_handler(CommandHandler("add",        add_expense))
    app.add_handler(CommandHandler("list",       list_expenses))
    app.add_handler(CommandHandler("budget",     set_budget))
    app.add_handler(CommandHandler("summary",    show_summary))
    app.add_handler(CommandHandler("projection", show_projection))
    app.add_handler(CommandHandler("alerts",     check_alerts))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CommandHandler("project",    project_command))

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
