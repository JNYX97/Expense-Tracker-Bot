# 💸 Personal Expense Tracker Bot

A Telegram bot to track monthly and annual expenses by period, set budgets, and project future spending.

---

## Categories

### 🗓 Monthly
`shopping` · `monthly subscription` · `food` · `transport` · `stipend`

### 📅 Annual
`insurance` · `investment` · `annual membership` · `project`

> To add/remove/rename categories, edit `categories.py` only.

---

## Commands

### Logging Expenses
| Command | Result |
|---|---|
| `/add 12.50 food Chicken rice` | Logs to current month (e.g. May 2026) |
| `/add 500 shopping Clothes --month June 2026` | Logs to June 2026 |
| `/add 500 shopping Clothes --month June` | Logs to June, current year |
| `/add 2000 project Malaysia Trip --year 2027` | Logs to annual 2027 |
| `/add 50 transport MRT --recurring 30` | Recurring every 30 days |

### Budgets
| Command | Result |
|---|---|
| `/budget food 400` | Set budget for current month |
| `/budget food 400 --month June 2026` | Set budget for June 2026 |
| `/budget insurance 1200` | Set annual budget for current year |
| `/budget insurance 1200 --year 2027` | Set annual budget for 2027 |

### Viewing
| Command | Result |
|---|---|
| `/list` | Expenses this month |
| `/list June 2026` | Expenses for June 2026 |
| `/list annual` | Expenses this year |
| `/list annual 2027` | Expenses for 2027 |
| `/summary` | Spending vs budget this month |
| `/summary June 2026` | Spending vs budget for June 2026 |
| `/summary annual` | Annual spending vs budget this year |
| `/summary annual 2027` | Annual spending vs budget for 2027 |
| `/projection 30` | Project next 30 days |
| `/alerts` | Budgets nearing limit (current period) |
| `/categories` | Show all valid categories |

---

## Setup (Windows)

```cmd
pip install -r requirements.txt
copy .env.example .env
notepad .env
python bot.py
```

---

## Deploy to Railway

1. Push this folder to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variable: `TELEGRAM_BOT_TOKEN = your_token_here`
4. Railway detects the Procfile and starts the bot ✅

---

## Project Structure

```
expense_bot/
├── bot.py           # Entry point
├── handlers.py      # All command logic
├── db.py            # Database queries
├── categories.py    # ← Edit this to change categories
├── parse_utils.py   # --month / --year flag parsing
├── requirements.txt
├── Procfile
└── .env.example
```
