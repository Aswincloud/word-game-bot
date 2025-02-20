from aiogram import types
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import ChatNotFound
from .misc import *

@dp.message_handler(commands="demote")
@admin_only
async def cmd_demote(message: types.Message) -> None:
    if not ADMIN_ID:
        await message.reply("No authorized users to remove.", allow_sending_without_reply=True)
        return

    args = message.get_args()
    if not args:
        await message.reply("Please provide a user ID.\nUsage: `/demote <user_id>`", parse_mode="Markdown", allow_sending_without_reply=True)
        return

    try:
        user_id = int(args.strip())
    except ValueError:
        await message.reply("Invalid user ID format. Please provide a valid numeric ID.", allow_sending_without_reply=True)
        return

    if user_id not in ADMIN_ID:
        await message.reply("User is not in the authorized list.", allow_sending_without_reply=True)
        return

    ADMIN_ID.remove(user_id)  # Remove user from the list

    try:
        user = await bot.get_chat(user_id)  # Fetch user details
        user_name = user.full_name
    except ChatNotFound:
        user_name = "Unknown"

    await message.reply(
        f"✅ User `{user_id}` - {user_name} has been demoted and removed from the authorized list.",
        parse_mode="Markdown",
        allow_sending_without_reply=True
    )