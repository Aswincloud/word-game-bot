from .misc import *
from aiogram.utils.callback_data import CallbackData

authorize_callback = CallbackData("authorize", "action", "entity_id", "admin_id")

@dp.message_handler(commands="authorize")
@admin_only
async def cmd_authorize(message: types.Message) -> None:
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
        elif message.reply_to_message.sender_chat:  # For groups/channels
            entity_id = message.reply_to_message.sender_chat.id

    if not entity_id:
        await message.reply(
            "⚠️ Usage: `/authorize <user_or_group_id>` or reply to a user's message with `/authorize`.\n\n"
            "Example:\n`/authorize 123456789` (for users)\nReply to a message with `/authorize` (to pick ID automatically)",
            parse_mode=types.ParseMode.MARKDOWN,
            allow_sending_without_reply=True
        )
        return

    # Prevent authorizing the owner (already authorized)
    if entity_id == OWNER_ID:
        await message.reply(
            "👑 **The owner is always authorized!** 🚀",
            parse_mode=types.ParseMode.MARKDOWN,
            allow_sending_without_reply=True
        )
        return

    # Check if already authorized
    if entity_id in ADMIN_ID or entity_id in AUTHORIZED_ID:
        await message.reply(
            "✅ This ID is already authorized.",
            allow_sending_without_reply=True
        )
        return

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Create confirmation buttons with admin_id restriction
    confirm_markup = InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=authorize_callback.new("confirm", entity_id, admin_id)),
        InlineKeyboardButton("❌ Cancel", callback_data=authorize_callback.new("cancel", entity_id, admin_id))
    )

    await message.reply(
        f"⚠️ Are you sure you want to authorize **{entity_name}** (`{entity_id}`)?",
        parse_mode=types.ParseMode.MARKDOWN,
        reply_markup=confirm_markup,
        allow_sending_without_reply=True
    )


# Callback handler for confirmation
@dp.callback_query_handler(authorize_callback.filter(action="confirm"))
async def confirm_authorize(callback_query: types.CallbackQuery, callback_data: dict):
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

    try:
        entity = await bot.get_chat(entity_id)  # Fetch user/group details
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Add to the appropriate authorization list
    if entity_id > 0:  # User
        ADMIN_ID.add(entity_id)
        entity_type = "User"
    else:  # Group
        AUTHORIZED_ID.add(entity_id)
        entity_type = "Group"

    await bot.edit_message_text(
        f"✅ {entity_type} `{entity_name}` (`{entity_id}`) has been **authorized** successfully.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )


# Callback handler for canceling authorization
@dp.callback_query_handler(authorize_callback.filter(action="cancel"))
async def cancel_authorize(callback_query: types.CallbackQuery, callback_data: dict):
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
        "❌ Authorization cancelled.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )