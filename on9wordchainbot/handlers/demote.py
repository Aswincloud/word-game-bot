from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .misc import *

@dp.message_handler(commands="demote")
@admin_only
async def cmd_demote(message: types.Message) -> None:
    entity_id = None

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

    # If no valid ID was found, show usage message
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
            "😡 **Don't dare to demote my owner!** 🚀",
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
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Create confirmation buttons
    confirm_markup = InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_demote:{entity_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_demote")
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote **{entity_name}** (`{entity_id}`)?",
        parse_mode=types.ParseMode.MARKDOWN,
        reply_markup=confirm_markup,
        allow_sending_without_reply=True
    )


# Callback handler for confirmation
@dp.callback_query_handler(lambda call: call.data.startswith("confirm_demote"))
async def confirm_demote(callback_query: types.CallbackQuery):
    entity_id = int(callback_query.data.split(":")[1])

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
        entity_name = entity.full_name if entity.type == "private" else entity.title
    except Exception:
        entity_name = "Unknown"

    # Remove from authorized lists
    if entity_id in ADMIN_ID:
        ADMIN_ID.remove(entity_id)
        entity_type = "User"
    elif entity_id in AUTHORIZED_ID:
        AUTHORIZED_ID.remove(entity_id)
        entity_type = "Group"
    else:
        await bot.answer_callback_query(
            callback_query.id, "This ID is not authorized.", show_alert=True
        )
        return

    await bot.edit_message_text(
        f"❌ {entity_type} `{entity_name}` (`{entity_id}`) has been **demoted** successfully.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )


# Callback handler for canceling demotion
@dp.callback_query_handler(lambda call: call.data == "cancel_demote")
async def cancel_demote(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        "❌ Demotion cancelled.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
    )
    

@dp.inline_handler()
async def inline_handler(inline_query: types.InlineQuery):
    text = inline_query.query.lower()
    if not text or inline_query.from_user.id not in VIP and (await amt_donated(inline_query.from_user.id)) < 10:
        results = []
        for mode in GAME_MODES:
            command = f"/{mode.command}@{(await bot.me).username}"
            results.append(
                types.InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="Start " + mode.name,
                    description=command,
                    input_message_content=types.InputTextMessageContent(command)
                )
            )
        await inline_query.answer(results, is_personal=not text)
        return

    if not is_word(text):
        await inline_query.answer(
            [
                types.InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="A query can only consist of alphabets",
                    description="Try a different query",
                    input_message_content=types.InputTextMessageContent(r"¯\\_(ツ)\_/¯")
                )
            ],
            is_personal=True
        )
        return

    res = []
    for word in Words.dawg.iterkeys(text):
        word = word.capitalize()
        res.append(
            types.InlineQueryResultArticle(
                id=str(uuid4()),
                title=word,
                input_message_content=types.InputTextMessageContent(word)
            )
        )
        if len(res) == 50:  # Max 50 results
            break

    if not res:  # No results
        res.append(
            types.InlineQueryResultArticle(
                id=str(uuid4()),
                title="No results found",
                description="Try a different query",
                input_message_content=types.InputTextMessageContent(r"¯\\_(ツ)\_/¯")
            )
        )

    await inline_query.answer(res, is_personal=True)


@dp.callback_query_handler()
async def callback_query_handler(callback_query: types.CallbackQuery) -> None:
    text = callback_query.data
    if text.startswith("donate"):
        await send_donate_invoice(callback_query.from_user.id, int(text.partition(":")[2]) * 100)
    await callback_query.answer()


@dp.errors_handler(exception=Exception)
async def error_handler(update: types.Update, error: TelegramAPIError) -> None:
    if update.message and update.message.chat:
        group_id = update.message.chat.id
        if group_id in GlobalState.games:
            asyncio.create_task(GlobalState.games[group_id].scan_for_stale_timer())

    # Unimportant errors
    if isinstance(error, (BotKicked, BotBlocked, CantInitiateConversation, InvalidQueryID)):
        return
    if isinstance(error, BadRequest) and str(error) in (
        "Have no rights to send a message",
        "Not enough rights to send text messages to the chat",
        "Group chat was deactivated",
        "Chat_write_forbidden",
        "Channel_private"
    ):
        return
    if isinstance(error, Unauthorized):
        if str(error).startswith("Forbidden: bot is not a member"):
            return
        if str(error).startswith("Forbidden: bot was kicked"):
            return
    if str(error).startswith("Internal Server Error: sent message was immediately deleted"):
        return

    if isinstance(error, MigrateToChat):  # TODO: Test
        # Migrate group running game and statistics
        if group_id in GlobalState.games:
            GlobalState.games[error.migrate_to_chat_id] = GlobalState.games.pop(group_id)
            GlobalState.games[error.migrate_to_chat_id].group_id = error.migrate_to_chat_id
            asyncio.create_task(
                send_admin_group(f"Game moved from {group_id} to {error.migrate_to_chat_id}.")
            )
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE game SET group_id = $1 WHERE group_id = $2;",
                error.migrate_to_chat_id, group_id
            )
            await conn.execute(
                "UPDATE gameplayer SET group_id = $1 WHERE group_id = $2;",
                error.migrate_to_chat_id, group_id
            )
            # await conn.execute("DELETE FROM game WHERE group_id = $1;", group_id)
            # await conn.execute("DELETE FROM gameplayer WHERE group_id = $1;", group_id)
        await send_admin_group(f"Group statistics migrated from {group_id} to {error.migrate_to_chat_id}.")
        return

    send_admin_msg = await send_admin_group(
        (
            f"<code>{error.__class__.__name__} @ "
            f"{group_id if update.message and update.message.chat else 'idk'}</code>:\n"
            f"<pre>{str(error)}</pre>"
        ) if isinstance(error, RetryAfter) else (
            "<pre>"
            + "".join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            + f"@ {group_id if update.message and update.message.chat else 'idk'}</pre>"
        ),
        parse_mode=types.ParseMode.HTML
    )
    if not update.message or not update.message.chat:
        return

    asyncio.create_task(
        update.message.reply(
            f"Error occurred (`{error.__class__.__name__}`). My owner has been notified.",
            allow_sending_without_reply=True
        )
    )

    if group_id in GlobalState.games:
        asyncio.create_task(
            send_admin_msg.reply(
                f"Killing game in {group_id} consequently.",
                allow_sending_without_reply=True
            )
        )
        GlobalState.games[group_id].state = GameState.KILLGAME
        await asyncio.sleep(2)

        # If game is still not terminated
        if group_id in GlobalState.games:
            del GlobalState.games[group_id]
            await update.message.reply("Game ended forcibly.", allow_sending_without_reply=True)
