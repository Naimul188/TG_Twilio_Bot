import asyncio
import logging
import os
import random
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from twilio.base.exceptions import TwilioRestException

import database
import twilio_helper

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Conversation States ─────────────────────────────────────────────────────
AWAITING_SID = 1
AWAITING_TOKEN = 2


# ─── Keyboards ───────────────────────────────────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Random Area Code", callback_data="random_area"),
            InlineKeyboardButton("🔍 Search Number", callback_data="search_number"),
        ],
        [InlineKeyboardButton("📥 View SMS / OTP", callback_data="view_sms")],
        [InlineKeyboardButton("📢 Set Group Forwarding", callback_data="set_group")],
        [InlineKeyboardButton("👤 Account Status & Balance", callback_data="account_status")],
    ])


def back_menu_btn() -> list:
    return [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data="back_menu")]


# ─── Auth helpers ─────────────────────────────────────────────────────────────

async def get_creds_or_notify(update: Update) -> dict | None:
    user_id = update.effective_user.id
    creds = await database.get_credentials(user_id)
    if not creds:
        query = update.callback_query
        text = "❌ আপনি লগইন করেননি। /start পাঠিয়ে লগইন করুন।"
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return None
    return creds


# ─── /start — Login flow entry ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    creds = await database.get_credentials(user_id)
    if creds:
        await update.message.reply_text(
            "✅ আপনি ইতিমধ্যে লগইন আছেন! নিচের মেনু থেকে অপশন বেছে নিন:",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 স্বাগতম! Twilio Bot-এ লগইন করতে প্রথমে আপনার\n"
        "Twilio *Account SID* লিখুন:",
        parse_mode="Markdown",
    )
    return AWAITING_SID


async def received_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_sid"] = update.message.text.strip()
    await update.message.reply_text(
        "এখন আপনার Twilio *Auth Token* লিখুন:",
        parse_mode="Markdown",
    )
    return AWAITING_TOKEN


async def received_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_sid = context.user_data.get("account_sid", "")
    auth_token = update.message.text.strip()
    user_id = update.effective_user.id

    msg = await update.message.reply_text("⏳ ক্রেডেনশিয়াল যাচাই করা হচ্ছে...")

    try:
        await twilio_helper.validate_credentials(account_sid, auth_token)
        await database.save_credentials(user_id, account_sid, auth_token)
        context.user_data.clear()

        await msg.edit_text(
            "✨ Twilio ক্রেডেনশিয়াল সফলভাবে সংরক্ষিত হয়েছে! ✨\n\n"
            "📱 পরবর্তী ধাপ:\n"
            "• নাম্বার কেনার জন্য 🌍 Random Area Code অথবা 🔍 Search Number এ ক্লিক দিন\n"
            "• উপলব্ধ নম্বর থেকে একটি কিনুন",
            reply_markup=main_menu_keyboard(),
        )
    except TwilioRestException as e:
        context.user_data.clear()
        await msg.edit_text(
            f"❌ ক্রেডেনশিয়াল যাচাই ব্যর্থ হয়েছে!\n"
            f"কারণ: {e.msg}\n\n"
            f"পুনরায় চেষ্টা করতে /start পাঠান।"
        )
    except Exception as e:
        context.user_data.clear()
        await msg.edit_text(
            f"❌ কোনো সমস্যা হয়েছে: {e}\n"
            f"পুনরায় চেষ্টা করতে /start পাঠান।"
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল করা হয়েছে।")
    return ConversationHandler.END


# ─── Callback Query Handler ───────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # ── Back to main menu ────────────────────────────────────────
    if data == "back_menu":
        context.user_data.clear()
        await query.edit_message_text(
            "🏠 মূল মেনু:",
            reply_markup=main_menu_keyboard(),
        )
        return

    # ── Account Status & Balance ─────────────────────────────────
    if data == "account_status":
        creds = await get_creds_or_notify(update)
        if not creds:
            return

        await query.edit_message_text("⏳ তথ্য লোড হচ্ছে...")
        try:
            info, bal = await asyncio.gather(
                twilio_helper.validate_credentials(creds["account_sid"], creds["auth_token"]),
                twilio_helper.get_balance(creds["account_sid"], creds["auth_token"]),
            )
            await query.edit_message_text(
                f"👤 *Account Status*\n\n"
                f"📛 নাম: {info['friendly_name']}\n"
                f"🔄 স্ট্যাটাস: {info['status']}\n"
                f"🏷️ টাইপ: {info['type']}\n"
                f"💰 ব্যালেন্স: {bal['balance']} {bal['currency']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except TwilioRestException as e:
            await query.edit_message_text(
                f"❌ তথ্য পাওয়া যায়নি: {e.msg}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ সমস্যা হয়েছে: {e}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )

    # ── Random Area Code ─────────────────────────────────────────
    elif data == "random_area":
        creds = await get_creds_or_notify(update)
        if not creds:
            return

        area_code = random.choice(twilio_helper.COMMON_AREA_CODES)
        await query.edit_message_text(
            f"🎲 এলোমেলো এরিয়া কোড বাছাই: *{area_code}*\n\n⏳ উপলব্ধ নম্বর খোঁজা হচ্ছে...",
            parse_mode="Markdown",
        )
        await _show_numbers_for_area(query, creds, area_code)

    # ── Search Number (prompt for area code) ─────────────────────
    elif data == "search_number":
        creds = await get_creds_or_notify(update)
        if not creds:
            return
        context.user_data["awaiting_area_code"] = True
        await query.edit_message_text(
            "🔍 অনুগ্রহ করে US এরিয়া কোড লিখুন (৩ সংখ্যা, যেমন: 212, 415, 312):"
        )

    # ── Buy number (show confirmation) ───────────────────────────
    elif data.startswith("buy_"):
        number = data[4:]
        context.user_data["pending_number"] = number
        await query.edit_message_text(
            f"📱 আপনি কি এই নম্বরটি কিনতে চান?\n\n*{number}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirm Buy", callback_data=f"confirm_buy_{number}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="back_menu"),
                ]
            ]),
        )

    # ── Confirm purchase ─────────────────────────────────────────
    elif data.startswith("confirm_buy_"):
        number = data[12:]
        creds = await get_creds_or_notify(update)
        if not creds:
            return

        await query.edit_message_text("⏳ নম্বর কেনা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")
        try:
            purchased = await twilio_helper.purchase_number(
                creds["account_sid"], creds["auth_token"], number
            )
            await query.edit_message_text(
                f"✅ আপনি সাফল্যের সাথে নাম্বার কিনেছেন: *{purchased}*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except TwilioRestException as e:
            await query.edit_message_text(
                f"❌ নম্বর কেনা ব্যর্থ হয়েছে!\n{e.msg}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ সমস্যা হয়েছে: {e}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )

    # ── View SMS / OTP — list numbers ────────────────────────────
    elif data == "view_sms":
        creds = await get_creds_or_notify(update)
        if not creds:
            return

        await query.edit_message_text("⏳ আপনার নম্বর সমূহ লোড হচ্ছে...")
        try:
            numbers = await twilio_helper.get_owned_numbers(
                creds["account_sid"], creds["auth_token"]
            )
            if not numbers:
                await query.edit_message_text(
                    "📭 আপনার কোনো সক্রিয় নম্বর নেই।",
                    reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
                )
                return

            buttons = [[InlineKeyboardButton(num, callback_data=f"sms_{num}")] for num in numbers]
            buttons.append(back_menu_btn())
            await query.edit_message_text(
                "📱 কোন নম্বরের SMS দেখতে চান?",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except TwilioRestException as e:
            await query.edit_message_text(
                f"❌ নম্বর লোড ব্যর্থ: {e.msg}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ সমস্যা হয়েছে: {e}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )

    # ── View SMS for specific number ─────────────────────────────
    elif data.startswith("sms_"):
        number = data[4:]
        creds = await get_creds_or_notify(update)
        if not creds:
            return

        await query.edit_message_text(f"⏳ {number} এর মেসেজ লোড হচ্ছে...")
        try:
            messages = await twilio_helper.get_messages(
                creds["account_sid"], creds["auth_token"], number
            )
            if not messages:
                await query.edit_message_text(
                    "📭 এখনো কোনো মেসেজ পাওয়া যায়নি।",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🔙 নম্বর তালিকায়", callback_data="view_sms"),
                            InlineKeyboardButton("🏠 মেনু", callback_data="back_menu"),
                        ]
                    ]),
                )
                return

            text = f"📨 *{number}* এর সাম্প্রতিক মেসেজ:\n\n"
            for msg in messages[:5]:
                text += (
                    f"👤 প্রেরক: `{msg['from']}`\n"
                    f"✉️ মেসেজ: {msg['body']}\n"
                    f"🕐 সময়: {msg['date_sent']}\n"
                    f"{'─' * 28}\n"
                )

            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔙 নম্বর তালিকায়", callback_data="view_sms"),
                        InlineKeyboardButton("🏠 মেনু", callback_data="back_menu"),
                    ]
                ]),
            )
        except TwilioRestException as e:
            await query.edit_message_text(
                f"❌ মেসেজ লোড ব্যর্থ: {e.msg}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ সমস্যা হয়েছে: {e}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )

    # ── Set Group Forwarding ─────────────────────────────────────
    elif data == "set_group":
        creds = await get_creds_or_notify(update)
        if not creds:
            return

        current_group = await database.get_group(user_id)
        text = "📢 *Group Forwarding সেটআপ*\n\n"
        if current_group:
            text += f"বর্তমান গ্রুপ: `{current_group}`\n\n"
        text += (
            "নতুন Telegram Group Chat ID লিখুন\n"
            "(যেমন: `-100xxxxxxxxxx`)\n\n"
            "⚠️ নিশ্চিত করুন বটটি সেই গ্রুপে যুক্ত আছে এবং মেসেজ পাঠানোর অনুমতি আছে।"
        )
        context.user_data["awaiting_group_id"] = True
        await query.edit_message_text(text, parse_mode="Markdown")


# ─── Number search helper ─────────────────────────────────────────────────────

async def _show_numbers_for_area(query, creds: dict, area_code: str):
    try:
        numbers = await twilio_helper.search_numbers(
            creds["account_sid"], creds["auth_token"], area_code
        )
        if not numbers:
            await query.edit_message_text(
                f"😔 {area_code} এরিয়া কোডে কোনো নম্বর পাওয়া যায়নি।",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
            return

        buttons = [[InlineKeyboardButton(num, callback_data=f"buy_{num}")] for num in numbers]
        buttons.append(back_menu_btn())
        await query.edit_message_text(
            f"📋 এরিয়া কোড *{area_code}*-এ উপলব্ধ নম্বরসমূহ:\nকিনতে একটিতে ক্লিক করুন:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except TwilioRestException as e:
        await query.edit_message_text(
            f"❌ নম্বর খোঁজা ব্যর্থ: {e.msg}",
            reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ সমস্যা হয়েছে: {e}",
            reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
        )


# ─── Text Message Handler (handles mid-flow text inputs) ─────────────────────

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ── Area code input ──────────────────────────────────────────
    if context.user_data.get("awaiting_area_code"):
        if not text.isdigit() or len(text) != 3:
            await update.message.reply_text(
                "❌ অবৈধ এরিয়া কোড। ঠিক ৩টি সংখ্যার এরিয়া কোড লিখুন (যেমন: 212):"
            )
            return  # keep state

        context.user_data.pop("awaiting_area_code", None)
        creds = await database.get_credentials(user_id)
        if not creds:
            await update.message.reply_text("❌ লগইন করুন। /start পাঠান।")
            return

        msg = await update.message.reply_text(
            f"⏳ এরিয়া কোড *{text}* এ নম্বর খোঁজা হচ্ছে...",
            parse_mode="Markdown",
        )

        try:
            numbers = await twilio_helper.search_numbers(
                creds["account_sid"], creds["auth_token"], text
            )
            if not numbers:
                await msg.edit_text(
                    f"😔 {text} এরিয়া কোডে কোনো নম্বর পাওয়া যায়নি।",
                    reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
                )
                return

            buttons = [[InlineKeyboardButton(num, callback_data=f"buy_{num}")] for num in numbers]
            buttons.append(back_menu_btn())
            await msg.edit_text(
                f"📋 এরিয়া কোড *{text}*-এ উপলব্ধ নম্বরসমূহ:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except TwilioRestException as e:
            await msg.edit_text(
                f"❌ নম্বর খোঁজা ব্যর্থ: {e.msg}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        except Exception as e:
            await msg.edit_text(
                f"❌ সমস্যা হয়েছে: {e}",
                reply_markup=InlineKeyboardMarkup([back_menu_btn()]),
            )
        return

    # ── Group ID input ───────────────────────────────────────────
    if context.user_data.get("awaiting_group_id"):
        # Basic format check: starts with - followed by digits
        if not (text.startswith("-") and text.lstrip("-").isdigit()):
            await update.message.reply_text(
                "❌ অবৈধ Group Chat ID। `-100xxxxxxxxxx` ফরম্যাটে লিখুন:",
                parse_mode="Markdown",
            )
            return  # keep state

        try:
            await context.bot.send_message(
                chat_id=int(text),
                text=(
                    "✅ Twilio Bot সংযুক্ত হয়েছে!\n"
                    "এই গ্রুপে নতুন SMS ফরওয়ার্ড করা হবে। 📩"
                ),
            )
            await database.save_group(user_id, text)
            context.user_data.pop("awaiting_group_id", None)
            await update.message.reply_text(
                f"✅ গ্রুপ সফলভাবে সেট হয়েছে!\nGroup ID: `{text}`\n\n"
                f"নতুন SMS এখন এই গ্রুপে ফরওয়ার্ড হবে।",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ গ্রুপে মেসেজ পাঠানো যায়নি!\n"
                f"নিশ্চিত করুন বট গ্রুপের সদস্য এবং মেসেজ পাঠানোর অনুমতি আছে।\n"
                f"কারণ: {e}\n\n"
                f"পুনরায় Group ID লিখুন:"
            )
        return

    # ── Default ──────────────────────────────────────────────────
    creds = await database.get_credentials(user_id)
    if creds:
        await update.message.reply_text(
            "🏠 মূল মেনু:",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "লগইন করতে /start পাঠান।"
        )


# ─── Background SMS Polling ───────────────────────────────────────────────────

async def poll_and_forward_sms(app: Application):
    """Poll Twilio every 30 s for new inbound SMS; forward to configured groups.

    Forwarding target priority (per user):
      1. Per-user group set via the bot UI (📢 Set Group Forwarding)
      2. Global GROUP_CHAT_ID from .env — applies to ALL users as a fallback
    """
    # Read global fallback group from environment
    env_group = os.environ.get("GROUP_CHAT_ID", "").strip() or None
    if env_group:
        logger.info("Global GROUP_CHAT_ID loaded from env: %s", env_group)
    else:
        logger.info("No global GROUP_CHAT_ID in env — only per-user groups will be used.")

    logger.info("SMS polling task started.")
    while True:
        try:
            users = await database.get_all_users_with_groups()
            for user in users:
                # Determine which group to forward to
                group_id = user["group_chat_id"] or env_group
                if not group_id:
                    continue  # no group configured for this user at all

                try:
                    messages = await twilio_helper.get_all_inbound_messages(
                        user["account_sid"], user["auth_token"]
                    )
                    for msg in messages:
                        if await database.is_message_forwarded(msg["sid"]):
                            continue

                        await database.mark_message_forwarded(msg["sid"], user["user_id"])

                        forward_text = (
                            "💬 নতুন ইনকামিং মেসেজ!\n"
                            f"📱 নাম্বার: {msg['to']}\n"
                            f"👤 প্রেরক: {msg['from']}\n"
                            f"✉️ মেসেজ: {msg['body']}"
                        )
                        try:
                            await app.bot.send_message(
                                chat_id=int(group_id),
                                text=forward_text,
                            )
                        except Exception as e:
                            logger.warning(
                                "Forward to group %s failed: %s",
                                group_id,
                                e,
                            )
                except TwilioRestException as e:
                    logger.warning("Twilio error for user %s: %s", user["user_id"], e)
                except Exception as e:
                    logger.warning("Error for user %s: %s", user["user_id"], e)
        except Exception as e:
            logger.error("Poll loop error: %s", e)

        await asyncio.sleep(30)


async def post_init(app: Application):
    asyncio.create_task(poll_and_forward_sms(app))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        sys.exit(1)

    asyncio.run(database.init_db())
    logger.info("Database initialised.")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AWAITING_SID: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_sid)],
            AWAITING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
