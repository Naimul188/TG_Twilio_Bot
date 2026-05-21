# Twilio Telegram Bot

A Telegram bot written in Python that integrates with the [Twilio](https://www.twilio.com/) API to manage US phone numbers, view incoming SMS/OTP messages, and automatically forward new SMS to a configured Telegram group.

Multiple users can log in simultaneously, each with their own Twilio credentials.

---

## Features

| Feature | Description |
|---|---|
| 🔐 Login | Authenticate with your Twilio Account SID + Auth Token |
| 🌍 Random Area Code | Browse available US numbers from a random area code |
| 🔍 Search Number | Search available numbers by a specific US area code |
| 📥 View SMS / OTP | See inbound messages for any of your Twilio numbers |
| 📢 Group Forwarding | Auto-forward new SMS to a Telegram group (polls every 30 s) |
| 👤 Account Status | View your Twilio account name, status, and balance |

All interface text is in **Bengali**.

---

## Requirements

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Twilio account (each user provides their own credentials inside the bot)

---

## Installation

```bash
git clone https://github.com/your-username/twilio-telegram-bot.git
cd twilio-telegram-bot
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file **or** export the variable directly:

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-from-botfather"
```

> **Never commit your bot token or any Twilio credentials to the repository.**

---

## Running

```bash
python3 main.py
```

The bot initialises a local SQLite database (`bot.db`) on first run and begins polling Telegram for updates.

---

## Project Structure

```
.
├── main.py            # Bot entrypoint — all handlers and polling loop
├── database.py        # Async SQLite helpers (aiosqlite)
├── twilio_helper.py   # Async wrappers around the Twilio REST SDK
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Architecture Notes

- **Async throughout** — uses `python-telegram-bot` v22 (async) with `asyncio`.
- **Twilio SDK calls** run inside `loop.run_in_executor` so they never block the event loop.
- **SMS forwarding** uses background polling every 30 seconds — no public webhook URL required.
- **Duplicate prevention** — forwarded message SIDs are stored in SQLite so the same SMS is never forwarded twice.
- **Multi-user** — credentials are stored per Telegram User ID; multiple users can be active simultaneously.

---

## Group Forwarding Setup

1. Add your bot to the target Telegram group.
2. In the bot, tap **📢 Set Group Forwarding**.
3. Enter the group's Chat ID (e.g. `-100xxxxxxxxxx`).
4. The bot sends a test message to verify access, then saves the mapping.

From that point, any new inbound SMS on your Twilio numbers will be forwarded to the group within ~30 seconds in this format:

```
💬 নতুন ইনকামিং মেসেজ!
📱 নাম্বার: +1xxxxxxxxxx
👤 প্রেরক: +1xxxxxxxxxx
✉️ মেসেজ: Your OTP is 123456
```

---

## License

MIT
