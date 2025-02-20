import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.executor import start_polling
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters import Command

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Replace with your actual bot token
TOKEN = "YOUR_BOT_TOKEN"
bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())  # Logs all bot interactions

# Replace with actual admin and owner IDs
OWNER_ID = 123456789  # Change to actual owner ID
ADMIN_ID = {987654321}  # Set of admin IDs
AUTHORIZED_ID = {555555555}  # Set of authorized user IDs

# Define callback data format
demote_callback = CallbackData("demote", "action", "entity_id", "admin_id")

@dp.message_handler(commands="demote")
async def cmd_demote(message: types.Message) -> None:
    """Handles /demote command with logging and debug prints."""
    logger.debug("[DEBUG] Received /demote command")
    
    entity_id = None
    admin_id = message.from_user.id  # Admin who initiated the command
    logger.debug(f"[DEBUG] Admin ID: {admin_id}")

    # Extract entity ID from command or reply
    args = message.text.split()
    if len(args) == 2 and args[1].isdigit():
        entity_id = int(args[1])
    elif message.reply_to_message:
        if message.reply_to_message.from_user:
            entity_id = message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:
            entity_id = message.reply_to_message.sender_chat.id

    if not entity_id:
        await message.reply(
            "⚠️ Usage: `/demote <user_or_group_id>` or reply to a user's message with `/demote`.",
            parse_mode=types.ParseMode.MARKDOWN
        )
        return

    # Prevent demoting the bot owner
    if entity_id == OWNER_ID:
        await message.reply("😡 **Don't dare to demote my owner!** 🚀", parse_mode=types.ParseMode.MARKDOWN)
        return

    # Check if the ID is authorized
    if entity_id not in ADMIN_ID and entity_id not in AUTHORIZED_ID:
        await message.reply("❌ This ID is not in the authorized list.")
        return

    try:
        entity = await bot.get_chat(entity_id)
        entity_name = entity.get_mention(as_html=True) if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    logger.debug(f"[DEBUG] Sending confirmation message for {entity_name} ({entity_id})")

    # Confirmation buttons
    confirm_markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Confirm", callback_data=demote_callback.new("confirm", entity_id, admin_id)),
        InlineKeyboardButton("❌ Cancel", callback_data=demote_callback.new("cancel", entity_id, admin_id))
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote {entity_name} (`{entity_id}`)?",
        parse_mode=types.ParseMode.HTML,
        reply_markup=confirm_markup
    )

@dp.callback_query_handler(demote_callback.filter(action="confirm"))
async def confirm_demote(callback_query: types.CallbackQuery, callback_data: dict):
    """Handles confirmation of demotion."""
    logger.debug("[DEBUG] Confirm button clicked!")
    logger.debug(f"[DEBUG] Callback Data: {callback_data}")

    entity_id = int(callback_data["entity_id"])
    admin_id = int(callback_data["admin_id"])

    if callback_query.from_user.id != admin_id:
        await bot.answer_callback_query(callback_query.id, "🚫 You are not allowed to confirm this action!", show_alert=True)
        return

    if entity_id == OWNER_ID:
        await bot.answer_callback_query(callback_query.id, "🚫 You cannot demote the owner!", show_alert=True)
        return

    try:
        entity = await bot.get_chat(entity_id)
        entity_name = entity.get_mention(as_html=True) if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    logger.debug(f"[DEBUG] Demoting {entity_name} ({entity_id})...")

    # Remove from admin lists
    ADMIN_ID.discard(entity_id)
    AUTHORIZED_ID.discard(entity_id)

    await bot.edit_message_text(
        f"❌ User {entity_name} (`{entity_id}`) has been **demoted** successfully.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.HTML
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(demote_callback.filter(action="cancel"))
async def cancel_demote(callback_query: types.CallbackQuery, callback_data: dict):
    """Handles cancellation of demotion."""
    logger.debug("[DEBUG] Cancel button clicked!")
    logger.debug(f"[DEBUG] Callback Data: {callback_data}")

    admin_id = int(callback_data["admin_id"])

    if callback_query.from_user.id != admin_id:
        await bot.answer_callback_query(callback_query.id, "🚫 You are not allowed to cancel this action!", show_alert=True)
        return

    await bot.edit_message_text(
        "❌ Demotion cancelled.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler()
async def catch_all_callbacks(callback_query: types.CallbackQuery):
    """Catches all callback queries for debugging."""
    logger.debug(f"[DEBUG] Raw callback received: {callback_query.data}")
    await bot.answer_callback_query(callback_query.id, "✅ Callback received!")
