import aiosqlite
import asyncio
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                account_sid TEXT NOT NULL,
                auth_token TEXT NOT NULL,
                group_chat_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forwarded_messages (
                message_sid TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_credentials(user_id: int, account_sid: str, auth_token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, account_sid, auth_token)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                account_sid = excluded.account_sid,
                auth_token = excluded.auth_token
        """, (user_id, account_sid, auth_token))
        await db.commit()


async def get_credentials(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_sid, auth_token FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"account_sid": row[0], "auth_token": row[1]}
            return None


async def save_group(user_id: int, group_chat_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET group_chat_id = ? WHERE user_id = ?",
            (group_chat_id, user_id)
        )
        await db.commit()


async def get_group(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT group_chat_id FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else None


async def get_all_users_with_groups():
    """Return all users, including those without a group (group_chat_id may be None)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, account_sid, auth_token, group_chat_id FROM users"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "user_id": r[0],
                    "account_sid": r[1],
                    "auth_token": r[2],
                    "group_chat_id": r[3],
                }
                for r in rows
            ]


async def is_message_forwarded(message_sid: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM forwarded_messages WHERE message_sid = ?",
            (message_sid,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def mark_message_forwarded(message_sid: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO forwarded_messages (message_sid, user_id) VALUES (?, ?)",
            (message_sid, user_id)
        )
        await db.commit()
