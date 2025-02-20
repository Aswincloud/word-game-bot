from aiogram.utils.callback_data import CallbackData
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .misc import dp, bot, OWNER_ID, ADMIN_ID, AUTHORIZED_ID, admin_only

# Define callback data format
demote_callback = CallbackData("demote", "action", "entity_id", "admin_id")

@dp.message_handler(commands="demote")
@admin_only
async def cmd_demote(message: types.Message) -> None:
    print("[DEBUG] Received /demote command")
    entity_id = None
    admin_id = message.from_user.id  # Admin who initiated the command
    print(f"[DEBUG] Admin ID: {admin_id}")

    # Extract entity ID from command or reply
    args = message.text.split()
    if len(args) == 2 and args[1].isdigit():
        entity_id = int(args[1])
    elif message.reply_to_message:
        if message.reply_to_message.from_user:
            entity_id = message.reply_to_message.from_user.id
        elif message.reply_to_message.sender_chat:
            entity_id = message.reply_to_message.sender_chat.id

    print(f"[DEBUG] Target Entity ID: {entity_id}")

    if not entity_id:
        await message.reply("⚠️ Invalid usage. Reply to a user or provide an ID.", parse_mode=types.ParseMode.MARKDOWN)
        return

    if entity_id == OWNER_ID:
        await message.reply("😡 You cannot demote the owner!", parse_mode=types.ParseMode.MARKDOWN)
        return

    if entity_id not in ADMIN_ID and entity_id not in AUTHORIZED_ID:
        await message.reply("❌ This ID is not in the authorized list.", allow_sending_without_reply=True)
        return

    try:
        entity = await bot.get_chat(entity_id)
        entity_name = entity.get_mention(as_html=True) if entity.type == "private" else entity.title
    except Exception as e:
        print(f"[DEBUG] Error fetching chat: {e}")
        entity_name = "Unknown"

    print(f"[DEBUG] Sending confirmation message for {entity_name} ({entity_id})")

    confirm_markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Confirm", callback_data=demote_callback.new("confirm", entity_id, admin_id)),
        InlineKeyboardButton("❌ Cancel", callback_data=demote_callback.new("cancel", entity_id, admin_id))
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote {entity_name} (`{entity_id}`)?",
        parse_mode=types.ParseMode.HTML,
        reply_markup=confirm_markup
    )


@dp.callback_query_handler()
async def catch_all_callbacks(callback_query: types.CallbackQuery):
    """Logs raw callback data before processing."""
    print(f"[DEBUG] Button clicked! Callback data received: {callback_query.data}")

    # Ensure correct callback parsing
    callback_parts = callback_query.data.split(":")
    if callback_parts[0] != "demote":
        print("[DEBUG] Callback does not match 'demote' prefix. Ignoring.")
        return

    action = callback_parts[1]
    entity_id = callback_parts[2]
    admin_id = callback_parts[3]

    print(f"[DEBUG] Parsed Callback - Action: {action}, Entity ID: {entity_id}, Admin ID: {admin_id}")


@dp.callback_query_handler(demote_callback.filter(action="confirm"))
async def confirm_demote(callback_query: types.CallbackQuery, callback_data: dict):
    """Handles demotion confirmation."""
    print("[DEBUG] ✅ Confirm button clicked!")

    entity_id = int(callback_data["entity_id"])
    admin_id = int(callback_data["admin_id"])

    print(f"[DEBUG] Entity ID: {entity_id}, Admin ID: {admin_id}")

    if callback_query.from_user.id != admin_id:
        print("[DEBUG] 🚨 Unauthorized confirm attempt!")
        await bot.answer_callback_query(callback_query.id, "🚫 You are not allowed to confirm this action!", show_alert=True)
        return

    if entity_id == OWNER_ID:
        await bot.answer_callback_query(callback_query.id, "🚫 You cannot demote the owner!", show_alert=True)
        return

    try:
        entity = await bot.get_chat(entity_id)
        entity_name = entity.get_mention(as_html=True) if entity.type == "private" else entity.title
    except Exception as e:
        print(f"[DEBUG] Error fetching chat: {e}")
        entity_name = "Unknown"

    ADMIN_ID.discard(entity_id)
    AUTHORIZED_ID.discard(entity_id)

    print(f"[DEBUG] ✅ {entity_name} ({entity_id}) demoted successfully!")

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
    print("[DEBUG] ❌ Cancel button clicked!")

    admin_id = int(callback_data["admin_id"])

    if callback_query.from_user.id != admin_id:
        print("[DEBUG] 🚨 Unauthorized cancel attempt!")
        await bot.answer_callback_query(callback_query.id, "🚫 You are not allowed to cancel this action!", show_alert=True)
        return

    await bot.edit_message_text(
        "❌ Demotion cancelled.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )
    await bot.answer_callback_query(callback_query.id)