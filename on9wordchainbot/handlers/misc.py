import asyncio
import traceback
import subprocess
from uuid import uuid4
from functools import wraps
import os
import signal
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData

from aiogram import types
from aiogram.dispatcher.filters import ChatTypeFilter, CommandStart
from aiogram.utils.exceptions import (BadRequest, BotBlocked, BotKicked, CantInitiateConversation, InvalidQueryID,
                                      MigrateToChat, RetryAfter, TelegramAPIError, Unauthorized)

from .donation import send_donate_invoice
from .. import GlobalState, bot, dp, pool
from ..constants import ADMIN_GROUP_ID, GameState, OFFICIAL_GROUP_ID, VIP, BOT_DIR, ADMIN_ID, AUTHORIZED_ID, OWNER_ID
from ..models import GAME_MODES
from ..utils import ADD_TO_GROUP_KEYBOARD, amt_donated, is_word, send_admin_group
from ..words import Words


@dp.message_handler(CommandStart(), ChatTypeFilter([types.ChatType.PRIVATE]))
async def cmd_start(message: types.Message) -> None:
    await message.reply(
        (
            "Hi! I host games of word chain in Telegram groups and I am made by @Aswin4122001.\n"
        ),
        allow_sending_without_reply=True,
        reply_markup=ADD_TO_GROUP_KEYBOARD
    )

def admin_only(f):
    """Decorator to check if the user is an admin."""
    @wraps(f)
    async def wrapped(message: types.Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_ID:
            await message.reply(
                "⛔ You are not authorized to use this command!",
                allow_sending_without_reply=True
            )
            return
        return await f(message, *args, **kwargs)
    return wrapped

@dp.message_handler(commands="feedback")
async def cmd_feedback(message: types.Message) -> None:
    rmsg = message.reply_to_message
    if (
        message.chat.id < 0
        and not message.get_command().partition("@")[2]
        and (not rmsg or rmsg.from_user.id != bot.id)
        or message.forward_from
    ):  # Prevent receiving feedback for other bots
        return

    arg = message.get_full_command()[1]
    if not arg:
        await message.reply(
            (
                "Function: Send feedback to my owner.\n"
                f"Usage: `/feedback@{(await bot.me).username} feedback`"
            ),
            allow_sending_without_reply=True
        )
        return

    asyncio.create_task(message.forward(ADMIN_GROUP_ID))
    asyncio.create_task(message.reply("Feedback sent successfully.", allow_sending_without_reply=True))


@dp.message_handler(commands="maintmode")
@admin_only
async def cmd_maintmode(message: types.Message) -> None:
    GlobalState.maint_mode = not GlobalState.maint_mode
    await message.reply(
        f"Maintenance mode has been switched {'on' if GlobalState.maint_mode else 'off'}.",
        allow_sending_without_reply=True
    )

@dp.message_handler(commands=["authorized_users", "au"])
@admin_only
async def cmd_authorized_users(message: types.Message) -> None:
    if not ADMIN_ID:
        await message.reply("No authorized users.", allow_sending_without_reply=True)
        return

    user_list = []
    for user_id in ADMIN_ID:
        try:
            user = await bot.get_chat(user_id)  # Fetch user details
            user_list.append(f"👤 `{user_id}` - [{user.full_name}](tg://user?id={user_id})")
        except Exception as e:
            user_list.append(f"👤 `{user_id}` - Name not found")

    await message.reply(
        f"👤 **Authorized Users:**\n" + "\n".join(user_list),
        parse_mode=types.ParseMode.MARKDOWN,
        allow_sending_without_reply=True
    )

@dp.message_handler(commands=["authorized_groups", "ag"])
@admin_only
async def cmd_authorized_groups(message: types.Message) -> None:
    if not AUTHORIZED_ID:
        await message.reply("No authorized groups.", allow_sending_without_reply=True)
        return

    group_list = []
    for group_id in AUTHORIZED_ID:
        try:
            group = await bot.get_chat(group_id)  # Fetch group details
            group_list.append(f"📢 `{group_id}` - *{group.title}*")
        except Exception as e:
            group_list.append(f"📢 `{group_id}` - Name not found")

    await message.reply(
        f"📢 **Authorized Groups:**\n" + "\n".join(group_list),
        parse_mode=types.ParseMode.MARKDOWN,
        allow_sending_without_reply=True
    )


@dp.message_handler(commands="restart")
@admin_only
async def cmd_restart(message: types.Message) -> None:
    await message.reply(
        "Updating and restarting the bot...",
        allow_sending_without_reply=True
    )

    # Run git pull to fetch the latest changes
    subprocess.run(["git", "pull"], cwd=BOT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Kill the current process
    os.kill(os.getpid(), signal.SIGTERM)


@dp.message_handler(
    ChatTypeFilter([types.ChatType.GROUP, types.ChatType.SUPERGROUP]), commands="leave"
)
@admin_only
async def cmd_leave(message: types.Message) -> None:
    await message.chat.leave()


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

    # Create confirmation buttons with admin_id restriction
    confirm_markup = InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=demote_callback.new("confirm", entity_id, admin_id)),
        InlineKeyboardButton("❌ Cancel", callback_data=demote_callback.new("cancel", entity_id, admin_id))
    )

    await message.reply(
        f"⚠️ Are you sure you want to demote [{entity_name}](tg://user?id={entity_id}) (`{entity_id}`)?",
        parse_mode=types.ParseMode.MARKDOWN,
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
            "😡 **Don't dare to demote my owner!** 🚀\n Better demote yourself!",
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
    async with pool.acquire() as conn:
        if entity_id > 0:  # User
            await conn.execute("DELETE FROM admin_id WHERE user_id = $1;", entity_id)
        else:  # Group
            await conn.execute("DELETE FROM authorized_id WHERE group_id = $1;", entity_id)

    await bot.edit_message_text(
        f"❌ {entity_type} [{entity_name}](tg://user?id={entity_id}) (`{entity_id}`) has been **demoted** successfully.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode=types.ParseMode.MARKDOWN
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


authorize_callback = CallbackData("authorize", "action", "entity_id", "admin_id")

@dp.message_handler(commands="authorize")
@admin_only
async def cmd_authorize(message: types.Message) -> None:
    entity_id = None
    admin_id = message.from_user.id  # Admin who initiated the command

    # If command is used with an ID
    args = message.text.split()
    if len(args) == 2 and args[1]:
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
        f"⚠️ Are you sure you want to authorize [{entity_name}](tg://user?id={entity_id})?",
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
        ADMIN_ID.append(entity_id)
        entity_type = "User"
    else:  # Group
        AUTHORIZED_ID.append(entity_id)
        entity_type = "Group"
    async with pool.acquire() as conn:
        if entity_id > 0:  # User
            await conn.execute("INSERT INTO admin_id (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING;", entity_id)
        else:  # Group
            await conn.execute("INSERT INTO authorized_id (group_id) VALUES ($1) ON CONFLICT (group_id) DO NOTHING;", entity_id)

    await bot.edit_message_text(
        f"✅ {entity_type} [{entity_name}](tg://user?id={entity_id}) (`{entity_id}`) has been **authorized** successfully.",
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

    
@dp.message_handler(commands="sql")
@admin_only
async def cmd_sql(message: types.Message) -> None:
    try:
        async with pool.acquire() as conn:
            res = await conn.fetch(message.get_full_command()[1])
    except Exception as e:
        await message.reply(f"`{e.__class__.__name__}: {str(e)}`", allow_sending_without_reply=True)
        return

    if not res:
        await message.reply("No results returned.", allow_sending_without_reply=True)
        return

    text = ["*" + " - ".join(res[0].keys()) + "*"]
    for r in res:
        text.append("`" + " - ".join(str(i) for i in r.values()) + "`")
    await message.reply("\n".join(text), allow_sending_without_reply=True)


@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member(message: types.Message) -> None:
    if any(user.id == bot.id for user in message.new_chat_members):  # self added to group
        await message.reply(
            "Thanks for adding me.\n Ash bot welcomes you!\n Start a classic game with /startclassic!",
            reply=False
        )
    elif message.chat.id == OFFICIAL_GROUP_ID:
        await message.reply(
            (
                "Welcome to the Word Chain game made by Ash!\n"
            ),
            allow_sending_without_reply=True
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
