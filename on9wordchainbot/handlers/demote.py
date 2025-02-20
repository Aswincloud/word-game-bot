from aiogram.utils.callback_data import CallbackData
from aiogram import types
from .misc import *

demote_callback = CallbackData("demote", "action", "entity_id", "admin_id")

@dp.message_handler(commands="demote")
@admin_only
async def cmd_demote(message: types.Message) -> None:
    entity_id = None
    admin_id = message.from_user.id  # Admin who initiated the command

    # If command is used with an ID
    args = message.text.split()
    if len(args) == 2 and args[1].isdigit():
        entity_id = int(args[1])

    # If the command is used as a reply, get the replied user's ID
    elif message.reply_to_message:
        if message.reply_to_message.from_user:
            entity_id = message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:  # For channels/supergroups
            entity_id = message.reply_to_message.sender_chat.id

    if not entity_id:
        await message.reply(
            "⚠️ Usage: `/demote <user_or_group_id>` or reply to a user's message with `/demote`.\n\n"
            "Example:\n`/demote 123456789` (for users)\nReply to a message with `/demote` (to pick ID automatically)",
            parse_mode=types.ParseMode.MARKDOWN,
            allow_sending_without_reply=True
        )
        return

    # Prevent demoting the bot owner
    if entity_id == OWNER_ID:
        await message.reply(
            "😡 **Don't dare to demote my owner!** 🚀\n Better demote yourself!",
            parse_mode=types.ParseMode.MARKDOWN,
            allow_sending_without_reply=True
        )
        return

    # Check if the ID is actually authorized
    if entity_id not in ADMIN_ID and entity_id not in AUTHORIZED_ID:
        await message.reply(
            "❌ This ID is not in the authorized list.", allow_sending_without_reply=True
        )
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.mention_html() if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Create confirmation buttons restricted to the admin who issued the command
    confirm_markup = InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=demote_callback.new("confirm", entity_id, admin_id)),
        InlineKeyboardButton("❌ Cancel", callback_data=demote_callback.new("cancel", entity_id, admin_id))
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote {entity_name} (`{entity_id}`)?",
        parse_mode=types.ParseMode.HTML,
        reply_markup=confirm_markup,
        allow_sending_without_reply=True
    )


# Callback handler for confirmation
@dp.callback_query_handler(demote_callback.filter(action="confirm"))
async def confirm_demote(callback_query: types.CallbackQuery, callback_data: dict):
    entity_id = int(callback_data["entity_id"])
    admin_id = int(callback_data["admin_id"])

    # Restrict button clicks to the admin who issued the command
    if callback_query.from_user.id != admin_id:
        await bot.answer_callback_query(
            callback_query.id,
            "🚫 You are not allowed to confirm this action!",
            show_alert=True
        )
        return

    # Ensure owner is not demoted (Extra Safety)
    if entity_id == OWNER_ID:
        await bot.answer_callback_query(
            callback_query.id,
            "🚫 You cannot demote the owner!",
            show_alert=True
        )
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.mention_html() if entity.type == "private" else entity.title
    except Exception as e:
        entity_name = "Unknown"
        await bot.answer_callback_query(
            callback_query.id, f"⚠️ Error fetching details: {e}", show_alert=True
        )
        return

    # Remove from authorized lists
    if entity_id in ADMIN_ID:
        ADMIN_ID.discard(entity_id)  # Use discard instead of remove
        entity_type = "User"
    elif entity_id in AUTHORIZED_ID:
        AUTHORIZED_ID.discard(entity_id)
        entity_type = "Group"
    else:
        await bot.answer_callback_query(
            callback_query.id, "This ID is not authorized.", show_alert=True
        )
        return

    await bot.edit_message_text(
        f"❌ {entity_type} {entity_name} (`{entity_id}`) has been **demoted** successfully.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.HTML
    )


# Callback handler for canceling demotion
@dp.callback_query_handler(demote_callback.filter(action="cancel"))
async def cancel_demote(callback_query: types.CallbackQuery, callback_data: dict):
    admin_id = int(callback_data["admin_id"])

    # Restrict button clicks to the admin who issued the command
    if callback_query.from_user.id != admin_id:
        await bot.answer_callback_query(
            callback_query.id,
            "🚫 You are not allowed to cancel this action!",
            show_alert=True
        )
        return

    await bot.edit_message_text(
        "❌ Demotion cancelled.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )