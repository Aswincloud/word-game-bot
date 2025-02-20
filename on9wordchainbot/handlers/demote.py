from aiogram import types
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import ChatNotFound
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

    try:
        user = await bot.get_chat(user_id)  # Fetch user details
        user_name = user.full_name
    except ChatNotFound:
        user_name = "Unknown"

    # Create confirmation buttons
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_demote_{user_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_demote_{user_id}")
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote `{user_id}` - {user_name}?",
        parse_mode="Markdown",
        reply_markup=keyboard,
        allow_sending_without_reply=True
    )

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_demote_"))
async def confirm_demote(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[-1])

    if user_id in ADMIN_ID:
        ADMIN_ID.remove(user_id)  # Remove user from the admin list
        await callback_query.message.edit_text(
            f"✅ User `{user_id}` has been demoted successfully.",
            parse_mode="Markdown"
        )
    else:
        await callback_query.message.edit_text(
            "❌ User is not in the authorized list or has already been removed.",
            parse_mode="Markdown"
        )

    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_demote_"))
async def cancel_demote(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("❌ Demotion cancelled.")
    await callback_query.answer()