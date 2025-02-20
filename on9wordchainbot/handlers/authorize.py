from aiogram import types, exceptions
from aiogram.utils.callback_data import CallbackData
from enum import Enum
import logging
from .misc import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

authorize_callback = CallbackData("authorize", "action", "entity_id", "admin_id")

class AuthorizeAction(Enum):
    CONFIRM = "confirm"
    CANCEL = "cancel"

@dp.message_handler(commands="authorize")
@admin_only
async def cmd_authorize(message: types.Message) -> None:
    """
    Handle the /authorize command.
    Allows an admin to authorize a user or group by ID or by replying to a message.
    """
    entity_id = None
    admin_id = message.from_user.id

    # Parse entity ID from command or reply
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
            "⚠️ Usage: `/authorize <user_or_group_id>` or reply to a user's message with `/authorize`.",
            parse_mode=types.ParseMode.MARKDOWN
        )
        return

    if entity_id == OWNER_ID:
        await message.reply("👑 **The owner is always authorized!** 🚀", parse_mode=types.ParseMode.MARKDOWN)
        return

    if entity_id in AUTHORIZED_ENTITIES:
        await message.reply("✅ This ID is already authorized.")
        return

    try:
        entity = await bot.get_chat(entity_id)
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except exceptions.ChatNotFound:
        await message.reply("❌ The specified ID does not exist or is inaccessible.")
        return
    except exceptions.TelegramAPIError as e:
        await message.reply(f"❌ An error occurred: {e}")
        return

    confirm_markup = InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=authorize_callback.new(AuthorizeAction.CONFIRM.value, entity_id, admin_id)),
        InlineKeyboardButton("❌ Cancel", callback_data=authorize_callback.new(AuthorizeAction.CANCEL.value, entity_id, admin_id))
    )

    await message.reply(
        f"⚠️ Are you sure you want to authorize **{entity_name}** (`{entity_id}`)?",
        parse_mode=types.ParseMode.MARKDOWN,
        reply_markup=confirm_markup
    )